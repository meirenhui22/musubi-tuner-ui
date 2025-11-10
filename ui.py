import subprocess
import threading
import time
import os
import psutil  # 新增：用于终止进程树
from datetime import datetime
import gradio as gr
import queue
import sys
import io

class TrainingManager:
    def __init__(self):
        self.processes = []  # 存储所有创建的进程（含子进程）
        self.is_training = False
        self.log_content = []
        self.log_queue = queue.Queue()
    
    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_content.append(log_entry)
        self.log_queue.put(log_entry)
        print(log_entry)
        return "\n".join(self.log_content[-20:])
    
    def get_latest_logs(self):
        return "\n".join(self.log_content[-20:])
    
    def execute_command(self, command, log_prefix=""):
        try:
            self.add_log(f"[调试] 执行命令: {command}")
            # 关键：创建进程时指定start_new_session=True，便于后续终止子进程
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True  # 新增：让进程成为新会话 leader，方便终止所有子进程
            )
            self.processes.append(process)  # 收集所有进程
            self.add_log(f"[调试] 启动进程，PID: {process.pid}")
            
            # 实时读取输出
            for line in process.stdout:
                if line.strip():
                    self.add_log(f"{log_prefix}{line.strip()}")
            
            process.wait()
            self.add_log(f"[调试] 进程PID {process.pid} 退出，返回码: {process.returncode}")
            return process.returncode == 0
        except Exception as e:
            err_msg = f"错误: {str(e)}"
            self.add_log(err_msg)
            print(err_msg)
            return False
    
    def _terminate_process_tree(self, pid):
        """新增：终止进程及其所有子进程（跨平台）"""
        try:
            parent = psutil.Process(pid)
            # 获取所有子进程（含孙子进程）
            children = parent.children(recursive=True)
            # 先终止子进程
            for child in children:
                self.add_log(f"[调试] 终止子进程，PID: {child.pid}")
                child.terminate()
            # 再终止父进程
            self.add_log(f"[调试] 终止父进程，PID: {parent.pid}")
            parent.terminate()
            # 等待进程退出
            parent.wait(timeout=5)
            return True
        except psutil.NoSuchProcess:
            self.add_log(f"[调试] 进程PID {pid} 已不存在")
            return True
        except Exception as e:
            self.add_log(f"[调试] 终止进程PID {pid} 失败: {str(e)}")
            return False
    
    def stop_training(self):
        """重写：彻底终止所有训练相关进程"""
        if not self.is_training and len(self.processes) == 0:
            msg = "当前无训练进程在运行"
            self.add_log(msg)
            return msg, self.get_latest_logs()
        
        # 终止所有收集的进程及其子进程
        for process in self.processes:
            self._terminate_process_tree(process.pid)
        
        # 清空进程列表，重置训练状态
        self.processes = []
        self.is_training = False
        
        # 记录停止日志
        stop_msg = "训练已彻底停止（所有相关进程已终止）"
        self.add_log(stop_msg)
        print(stop_msg)
        return stop_msg, self.get_latest_logs()
    
    def start_training(self, config):
        if self.is_training:
            msg = "训练已在进行中！"
            print(msg)
            return msg, ""
        
        # 启动前先清空历史进程和日志
        self.processes = []
        self.log_content = []
        self.is_training = True
        
        # 模型路径配置（不变）
        if config['mode'] == 'qwen-image':
            dataset_config = config['dataset_config'] or './setting/qwen-image-setting.toml'
            dit_model = config['dit'] or './models/qwen_image_bf16.safetensors'
        else:
            dataset_config = config['dataset_config'] or './setting/qwen-edit-setting.toml'
            dit_model = config['dit'] or './models/qwen_image_edit_bf16.safetensors'
        
        text_encoder = config['text_encoder'] or './models/qwen_2.5_vl_7b.safetensors'
        vae = config['vae'] or './models/qwen_image_vae.safetensors'
        
        # 预缓存命令（不变）
        cache_latents_cmd = f"python musubi-tuner/src/musubi_tuner/qwen_image_cache_latents.py --dataset_config {dataset_config} --vae {vae}"
        cache_text_cmd = f"python musubi-tuner/src/musubi_tuner/qwen_image_cache_text_encoder_outputs.py --dataset_config {dataset_config} --text_encoder {text_encoder} --batch_size {config['batch_size']}"
        if config['fp8_vl']:
            cache_text_cmd += " --fp8_vl"
        
        # 训练命令（单行拼接）
        train_cmd = (
            f"accelerate launch "
            f"--num_cpu_threads_per_process 1 "
            f"--mixed_precision {config['mixed_precision']} "
            f"--num_processes 1 "
            f"--num_machines 1 "
            f"--dynamo_backend no "
            f"--gpu_ids 0 "
            f"musubi-tuner/src/musubi_tuner/qwen_image_train_network.py "
            f"--dit {dit_model} "
            f"--dataset_config {dataset_config} "
            f"--vae {vae} "
            f"--text_encoder {text_encoder} "
            f"--mixed_precision {config['mixed_precision']} "
            f"--optimizer_type {config['optimizer_type']} "
            f"--learning_rate {config['learning_rate']} "
            f"--gradient_checkpointing "
            f"--gradient_accumulation_steps {config['gradient_accumulation_steps']} "
            f"--max_data_loader_n_workers {config['max_data_loader_n_workers']} "
            f"--persistent_data_loader_workers "
            f"--network_module {config['network_module']} "
            f"--network_dim {config['network_dim']} "
            f"--timestep_sampling {config['timestep_sampling']} "
            f"--discrete_flow_shift {config['discrete_flow_shift']} "
            f"--max_train_epochs {config['max_train_epochs']} "
            f"--save_every_n_epochs {config['save_every_n_epochs']} "
            f"--output_dir {config['output_dir']} "
            f"--output_name {config['output_name']} "
            f"--seed {config['seed']} "
            f"--log_with tensorboard "
            f"--logging_dir {config['logging_dir']} "
            f"--lr_scheduler {config['lr_scheduler']} "
            f"--lr_warmup_steps {config['lr_warmup_steps']} "
            f"--sdpa "
            f"--blocks_to_swap {config['blocks_to_swap']} "
            f"--fp8_base "
            f"--sample_at_first"
        )
        
        if config['mode'] == 'qwen-image-edit':
            train_cmd += " --edit"
        if config['enable_sampling'] and config['sample_prompts']:
            train_cmd += f" --sample_prompts {config['sample_prompts']} --sample_every_n_epochs {config['sample_every_n_epochs']}"
        
        def run_training():
            try:
                self.add_log("开始执行预缓存VAE latents...")
                success = self.execute_command(cache_latents_cmd, "[VAE缓存] ")
                if not success:
                    self.add_log("VAE缓存失败，停止训练")
                    self.stop_training()  # 失败时调用停止逻辑
                    return
                
                self.add_log("开始执行预缓存文本编码器输出...")
                success = self.execute_command(cache_text_cmd, "[文本编码器缓存] ")
                if not success:
                    self.add_log("文本编码器缓存失败，停止训练")
                    self.stop_training()  # 失败时调用停止逻辑
                    return
                
                self.add_log("开始训练...")
                success = self.execute_command(train_cmd, "[训练] ")
                if success:
                    self.add_log("训练正常完成！")
                else:
                    self.add_log("训练过程异常退出")
            except Exception as e:
                err_msg = f"训练过程中出现异常: {str(e)}"
                self.add_log(err_msg)
                print(err_msg)
            finally:
                # 无论成功/失败，最终重置状态
                self.is_training = False
                self.add_log("训练流程结束（已重置训练状态）")
        
        thread = threading.Thread(target=run_training)
        thread.daemon = True
        thread.start()
        
        start_msg = "训练已启动！"
        self.add_log(start_msg)
        print(start_msg)
        return start_msg, self.get_latest_logs()

def create_interface():
    manager = TrainingManager()
    
    # 设置界面宽度为1200px
    with gr.Blocks(title="Qwen-Image训练参数配置器", css="""
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
        .gradio-button-primary { margin-right: 10px !important; }
        .gradio-row { margin-bottom: 15px !important; }
        .common-param-title { font-weight: bold; color: #2c3e50; margin: 10px 0 5px 0; }
    """) as demo:
        with gr.Column(elem_classes="container"):
            gr.Markdown("# Qwen-Image训练参数配置器")
            gr.Markdown("配置训练参数并启动训练（停止功能已修复）")

            # ======================================
            # 常用核心参数（不变）
            # ======================================
            gr.Markdown("## 常用核心参数", elem_classes="common-param-title")
            with gr.Row():
                with gr.Column(scale=1):
                    mode = gr.Radio(
                        choices=["qwen-image", "qwen-image-edit"],
                        value="qwen-image",
                        label="📌 训练模式",
                        interactive=True
                    )
                    gr.Markdown("### 核心模型路径")
                    dit = gr.Textbox(
                        label="DiT模型路径",
                        value="./models/qwen_image_bf16.safetensors",
                        placeholder="例如: ./models/qwen_image_bf16.safetensors",
                        interactive=True
                    )
                    gr.Markdown("<small>qwen-image: ./models/qwen_image_bf16.safetensors | qwen-image-edit: ./models/qwen_image_edit_bf16.safetensors</small>")
                    
                    vae = gr.Textbox(
                        label="VAE模型路径",
                        value="./models/qwen_image_vae.safetensors",
                        placeholder="例如: ./models/qwen_image_vae.safetensors",
                        interactive=True
                    )
                    text_encoder = gr.Textbox(
                        label="文本编码器路径",
                        value="./models/qwen_2.5_vl_7b.safetensors",
                        placeholder="例如: ./models/qwen_2.5_vl_7b.safetensors",
                        interactive=True
                    )

                with gr.Column(scale=1):
                    gr.Markdown("### 数据集与输出")
                    dataset_config = gr.Textbox(
                        label="数据集配置文件路径",
                        value="./setting/qwen-image-setting.toml",
                        placeholder="例如: ./setting/qwen-image-setting.toml",
                        interactive=True
                    )
                    gr.Markdown("<small>qwen-image: ./setting/qwen-image-setting.toml | qwen-image-edit: ./setting/qwen-edit-setting.toml</small>")
                    
                    output_dir = gr.Textbox(
                        label="输出目录（模型保存路径）",
                        value="./output",
                        placeholder="例如: ./output",
                        interactive=True
                    )
                    output_name = gr.Textbox(
                        label="模型保存名称",
                        value="qwen-image-loraname-v1",
                        placeholder="例如: qwen-image-my-model-v1",
                        interactive=True
                    )
                    logging_dir = gr.Textbox(
                        label="TensorBoard日志目录",
                        value="./logs",
                        placeholder="例如: ./logs（TensorBoard日志保存路径）",
                        interactive=True
                    )

            gr.Markdown("### 关键训练参数")
            with gr.Row():
                max_train_epochs = gr.Slider(
                    minimum=1, maximum=100, value=10, step=1,
                    label="训练轮数", interactive=True
                )
                learning_rate = gr.Textbox(
                    label="学习率", value="5e-5",
                    placeholder="例如: 5e-5（推荐默认）", interactive=True
                )
                mixed_precision = gr.Radio(
                    choices=["no", "fp16", "bf16"], value="bf16",
                    label="混合精度（影响速度/显存）", interactive=True
                )
            gr.Markdown("<small>学习率默认5e-5，混合精度推荐bf16（需显卡支持）</small>")

            # ======================================
            # 进阶配置参数（不变）
            # ======================================
            gr.Markdown("## 进阶配置参数", elem_classes="common-param-title")
            
            gr.Markdown("### 网络配置（LoRA相关）")
            with gr.Row():
                network_module = gr.Textbox(
                    label="网络模块", value="networks.lora_qwen_image",
                    placeholder="默认: networks.lora_qwen_image", interactive=True
                )
                network_dim = gr.Slider(
                    minimum=1, maximum=64, value=16, step=1,
                    label="LoRA维度（推荐16）", interactive=True
                )
            gr.Markdown("<small>LoRA维度越高，拟合能力越强但显存占用越高</small>")

            gr.Markdown("### 优化器与数据加载")
            with gr.Row():
                optimizer_type = gr.Radio(
                    choices=["adamw8bit", "adamw", "lion"], value="adamw8bit",
                    label="优化器类型", interactive=True
                )
                max_data_loader_n_workers = gr.Slider(
                    minimum=0, maximum=8, value=2, step=1,
                    label="数据加载线程数", interactive=True
                )
                batch_size = gr.Slider(
                    minimum=1, maximum=16, value=1, step=1,
                    label="缓存批次大小", interactive=True
                )
            fp8_vl = gr.Checkbox(
                label="FP8 VL（文本编码器显存优化）", value=True,
                interactive=True
            )

            gr.Markdown("### 高级配置（谨慎调整）")
            with gr.Row():
                timestep_sampling = gr.Radio(
                    choices=["uniform", "shift"], value="shift",
                    label="时间步采样方式", interactive=True
                )
                discrete_flow_shift = gr.Slider(
                    minimum=1.0, maximum=4.0, value=2.2, step=0.1,
                    label="离散流偏移值（默认2.2）", interactive=True
                )
            with gr.Row():
                gradient_accumulation_steps = gr.Slider(
                    minimum=1, maximum=16, value=1, step=1,
                    label="梯度累积步数", interactive=True
                )
                save_every_n_epochs = gr.Slider(
                    minimum=1, maximum=20, value=1, step=1,
                    label="每N轮保存模型", interactive=True
                )
                seed = gr.Number(
                    label="随机种子（默认42）", value=42,
                    interactive=True
                )
            blocks_to_swap = gr.Slider(
                minimum=0, maximum=32, value=24, step=1,
                label="块交换数量（显存优化，默认24）", interactive=True
            )

            gr.Markdown("### 采样配置（可选，非必须）")
            enable_sampling = gr.Checkbox(
                label="启用训练中采样", value=False,
                interactive=True
            )
            sample_prompts = gr.Textbox(
                label="采样提示文件路径", value="",
                placeholder="例如: ./prompts.txt（启用采样时必填）",
                interactive=True
            )
            sample_every_n_epochs = gr.Slider(
                minimum=1, maximum=10, value=1, step=1,
                label="每N轮采样一次", interactive=True
            )

            # ======================================
            # 训练控制与日志（不变，确保停止按钮绑定正确）
            # ======================================
            gr.Markdown("## 训练控制与日志", elem_classes="common-param-title")
            
            with gr.Row():
                start_btn = gr.Button("🚀 开始训练", variant="primary", size="lg")
                stop_btn = gr.Button("⏹️ 停止训练", variant="stop", size="lg")
            status = gr.Textbox(
                label="当前状态", value="未开始训练",
                interactive=False, lines=2
            )
            
            gr.Markdown("### 实时训练日志")
            logs = gr.TextArea(
                label="训练日志（最近20条）",
                interactive=False, lines=15,
                placeholder="训练启动后将显示实时日志..."
            )

            # 隐藏的刷新按钮
            refresh_btn = gr.Button("刷新日志", visible=False)

            # ======================================
            # 功能逻辑绑定（不变）
            # ======================================
            # 1. 训练模式切换更新路径
            def update_paths_for_mode(mode):
                if mode == "qwen-image":
                    return "./models/qwen_image_bf16.safetensors", "./setting/qwen-image-setting.toml"
                else:
                    return "./models/qwen_image_edit_bf16.safetensors", "./setting/qwen-edit-setting.toml"
            mode.change(update_paths_for_mode, inputs=[mode], outputs=[dit, dataset_config])

            # 2. 开始训练
            def start_training_wrapper(*args):
                config = {
                    'mode': args[0], 'dit': args[1], 'vae': args[2], 'text_encoder': args[3],
                    'dataset_config': args[4], 'network_module': args[5], 'network_dim': int(args[6]),
                    'mixed_precision': args[7], 'max_train_epochs': int(args[8]), 'learning_rate': args[9],
                    'timestep_sampling': args[10], 'discrete_flow_shift': float(args[11]),
                    'optimizer_type': args[12], 'max_data_loader_n_workers': int(args[13]),
                    'batch_size': int(args[14]), 'fp8_vl': args[15],
                    'output_dir': args[16], 'output_name': args[17], 'logging_dir': args[18],
                    'gradient_accumulation_steps': int(args[19]),
                    'save_every_n_epochs': int(args[20]), 'seed': int(args[21]),
                    'blocks_to_swap': int(args[22]), 'enable_sampling': args[23],
                    'sample_prompts': args[24], 'sample_every_n_epochs': int(args[25]),
                    'lr_scheduler': 'constant', 'lr_warmup_steps': 0
                }
                return manager.start_training(config)
            start_btn.click(
                start_training_wrapper,
                inputs=[
                    mode, dit, vae, text_encoder, dataset_config, network_module, network_dim,
                    mixed_precision, max_train_epochs, learning_rate, timestep_sampling, discrete_flow_shift,
                    optimizer_type, max_data_loader_n_workers, batch_size, fp8_vl,
                    output_dir, output_name, logging_dir,
                    gradient_accumulation_steps, save_every_n_epochs, seed,
                    blocks_to_swap, enable_sampling, sample_prompts, sample_every_n_epochs
                ],
                outputs=[status, logs]
            )

            # 3. 停止训练（绑定修复后的stop_training方法）
            def stop_training_wrapper():
                return manager.stop_training()
            stop_btn.click(stop_training_wrapper, outputs=[status, logs])

            # 4. 日志刷新
            def refresh_logs():
                return manager.get_latest_logs()
            refresh_btn.click(refresh_logs, outputs=logs)

            def auto_refresh_loop():
                while True:
                    refresh_btn.click()
                    time.sleep(1)
            def start_refresh_thread():
                refresh_thread = threading.Thread(target=auto_refresh_loop, daemon=True)
                refresh_thread.start()
            demo.load(start_refresh_thread)

    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)