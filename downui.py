import os
from flask import Flask, render_template_string, send_from_directory, request, abort, send_file
from datetime import datetime
import urllib.parse

app = Flask(__name__)

# 配置设置 - 可根据服务器环境调整
class Config:
    # 根目录配置（可设置为绝对路径或相对路径）
    ROOT_DIRECTORY = os.getcwd()  # 默认为当前工作目录
    # 或者设置为特定目录，例如：
    # ROOT_DIRECTORY = '/home/user/files'  # 绝对路径
    # ROOT_DIRECTORY = './files'          # 相对路径
    
    # 服务器设置
    HOST = '0.0.0.0'  # 允许所有网络接口访问
    PORT = 5001
    DEBUG = False  # 生产环境设为False
    
    # 安全设置
    ALLOWED_EXTENSIONS = None  # None表示允许所有文件类型，或设置为 ['txt', 'pdf', 'zip'] 等白名单
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 最大下载文件大小 (1GB)

# 定义 HTML 模板（优化版）
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>通用文件浏览器</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }
        h1 { 
            color: #2c3e50; 
            margin-top: 0;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .breadcrumb {
            background: #ecf0f1;
            padding: 10px 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .breadcrumb a {
            color: #3498db;
            text-decoration: none;
        }
        .breadcrumb a:hover {
            text-decoration: underline;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #34495e;
            color: white;
            font-weight: 600;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
        .directory { 
            color: #e74c3c; 
            font-weight: 600;
        }
        .file { 
            color: #2c3e50; 
        }
        .btn {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .btn-download {
            background-color: #27ae60;
            color: white;
        }
        .btn-download:hover {
            background-color: #219a52;
        }
        .file-info {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .icon {
            width: 20px;
            text-align: center;
        }
        .size { width: 120px; }
        .date { width: 200px; }
        .actions { width: 100px; }
        .search-box {
            margin-bottom: 20px;
        }
        .search-box input {
            padding: 8px 12px;
            width: 300px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        @media (max-width: 768px) {
            .container { padding: 10px; }
            th, td { padding: 8px 10px; }
            .size, .date { display: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 文件浏览器</h1>
        
        <div class="breadcrumb">
            <a href="{{ url_for('browse', path='') }}">根目录</a>
            {% for part in breadcrumbs %}
                <span> / </span>
                {% if not loop.last %}
                    <a href="{{ url_for('browse', path=part.path) }}">{{ part.name }}</a>
                {% else %}
                    <span>{{ part.name }}</span>
                {% endif %}
            {% endfor %}
        </div>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="搜索文件或文件夹..." onkeyup="filterItems()">
        </div>
        
        <table id="fileTable">
            <thead>
                <tr>
                    <th>名称</th>
                    <th class="size">大小</th>
                    <th class="date">修改日期</th>
                    <th class="actions">操作</th>
                </tr>
            </thead>
            <tbody>
                {% if parent_path is not none %}
                <tr class="directory-item">
                    <td colspan="4">
                        <div class="file-info">
                            <span class="icon">📁</span>
                            <a href="{{ url_for('browse', path=parent_path) }}">返回上一级</a>
                        </div>
                    </td>
                </tr>
                {% endif %}
                
                {% for item in items %}
                <tr class="{% if item.is_dir %}directory-item{% else %}file-item{% endif %}">
                    <td>
                        <div class="file-info">
                            <span class="icon">{% if item.is_dir %}📁{% else %}📄{% endif %}</span>
                            {% if item.is_dir %}
                                <a href="{{ url_for('browse', path=item.path) }}" class="directory">{{ item.name }}</a>
                            {% else %}
                                <span class="file">{{ item.name }}</span>
                            {% endif %}
                        </div>
                    </td>
                    <td class="size">{{ item.size }}</td>
                    <td class="date">{{ item.modified }}</td>
                    <td class="actions">
                        {% if not item.is_dir %}
                            <a href="{{ url_for('download', path=item.path) }}" class="btn btn-download">下载</a>
                        {% else %}
                            <span>—</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if not items and parent_path is not none %}
        <div style="text-align: center; padding: 40px; color: #7f8c8d;">
            此文件夹为空
        </div>
        {% endif %}
    </div>

    <script>
        function filterItems() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const rows = document.querySelectorAll('#fileTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        // 自动聚焦搜索框
        document.addEventListener('DOMContentLoaded', function() {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) searchInput.focus();
        });
    </script>
</body>
</html>
"""

class FileItem:
    def __init__(self, name, path, is_dir, size, modified):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.size = size
        self.modified = modified

class BreadcrumbPart:
    def __init__(self, name, path):
        self.name = name
        self.path = path

def get_safe_path(requested_path):
    """确保路径安全，防止目录遍历攻击"""
    # 规范化路径并确保它在根目录内
    requested_path = requested_path or ''
    
    # 处理路径中的特殊字符和目录遍历尝试
    clean_path = os.path.normpath('/' + requested_path).lstrip('/')
    
    # 构建完整路径
    full_path = os.path.join(Config.ROOT_DIRECTORY, clean_path)
    full_path = os.path.abspath(full_path)
    
    # 安全检查：确保路径仍在根目录内
    if not full_path.startswith(Config.ROOT_DIRECTORY):
        abort(403, description="禁止访问：路径安全检查失败")
    
    return clean_path, full_path

@app.route('/')
def index():
    """首页重定向到浏览根目录"""
    return browse('')

@app.route('/browse/')
@app.route('/browse/<path:path>')
def browse(path):
    """浏览目录内容"""
    try:
        clean_path, full_path = get_safe_path(path)
        
        # 检查路径是否存在
        if not os.path.exists(full_path):
            abort(404, description="路径不存在")
        
        # 如果是文件，直接提供下载
        if os.path.isfile(full_path):
            return download(path)
        
        # 构建面包屑导航
        breadcrumbs = [BreadcrumbPart('根目录', '')]
        accumulated_path = ''
        
        if clean_path:
            for part in clean_path.split('/'):
                accumulated_path = accumulated_path + '/' + part if accumulated_path else part
                breadcrumbs.append(BreadcrumbPart(part, accumulated_path))
        
        # 获取父目录路径
        parent_path = os.path.dirname(clean_path) if clean_path else None
        if parent_path == '':
            parent_path = None
        
        # 获取目录内容
        items = []
        try:
            for entry in os.scandir(full_path):
                try:
                    if entry.is_dir():
                        size = '-'
                    else:
                        # 检查文件大小限制
                        file_size = entry.stat().st_size
                        if file_size > Config.MAX_FILE_SIZE:
                            size = "文件过大"
                        else:
                            size = format_size(file_size)
                    
                    modified = format_timestamp(entry.stat().st_mtime)
                    
                    # 构建相对路径
                    item_path = os.path.join(clean_path, entry.name) if clean_path else entry.name
                    
                    items.append(FileItem(
                        name=entry.name,
                        path=item_path,
                        is_dir=entry.is_dir(),
                        size=size,
                        modified=modified
                    ))
                except (PermissionError, OSError) as e:
                    # 记录无法访问的文件/目录
                    print(f"无法访问 {entry.name}: {str(e)}")
                    continue
                    
        except PermissionError as e:
            abort(403, description=f"没有权限访问目录: {str(e)}")
        except FileNotFoundError as e:
            abort(404, description="目录不存在")
        except OSError as e:
            abort(500, description=f"访问目录时出错: {str(e)}")
        
        # 按类型和名称排序（目录在前）
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        
        return render_template_string(
            HTML_TEMPLATE, 
            items=items, 
            path=clean_path,
            parent_path=parent_path,
            breadcrumbs=breadcrumbs
        )
        
    except Exception as e:
        abort(500, description=f"服务器错误: {str(e)}")

@app.route('/download/<path:path>')
def download(path):
    """下载文件"""
    try:
        clean_path, full_path = get_safe_path(path)
        
        # 确保路径是文件而不是目录
        if not os.path.isfile(full_path):
            abort(404, description="文件不存在")
        
        # 检查文件大小
        file_size = os.path.getsize(full_path)
        if file_size > Config.MAX_FILE_SIZE:
            abort(413, description="文件过大，无法下载")
        
        # 检查文件扩展名（如果设置了白名单）
        if Config.ALLOWED_EXTENSIONS:
            file_ext = os.path.splitext(full_path)[1].lower().lstrip('.')
            if file_ext not in Config.ALLOWED_EXTENSIONS:
                abort(403, description="不允许下载此类型文件")
        
        # 安全地提供文件下载
        directory, filename = os.path.split(full_path)
        return send_from_directory(
            directory, 
            filename, 
            as_attachment=True,
            download_name=filename  # 指定下载时的文件名
        )
        
    except PermissionError:
        abort(403, description="没有文件访问权限")
    except FileNotFoundError:
        abort(404, description="文件不存在")
    except Exception as e:
        abort(500, description=f"下载文件时出错: {str(e)}")

def format_size(size_bytes):
    """将字节大小转换为人类可读的格式"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f} {size_names[i]}"

def format_timestamp(timestamp):
    """将时间戳转换为可读的日期时间格式"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

@app.errorhandler(403)
def forbidden_error(error):
    return f"<h1>403 禁止访问</h1><p>{error.description}</p>", 403

@app.errorhandler(404)
def not_found_error(error):
    return f"<h1>404 未找到</h1><p>{error.description}</p>", 404

@app.errorhandler(413)
def too_large_error(error):
    return f"<h1>文件过大</h1><p>{error.description}</p>", 413

@app.errorhandler(500)
def internal_error(error):
    return f"<h1>500 服务器内部错误</h1><p>{error.description}</p>", 500

if __name__ == '__main__':
    # 创建示例目录结构（可选）
    # os.makedirs('example_files', exist_ok=True)
    # with open('example_files/readme.txt', 'w') as f:
    #     f.write('这是一个示例文件。您可以将您的文件放在此目录中。')
    
    print(f"文件浏览器服务已启动!")
    print(f"访问地址: http://{Config.HOST}:{Config.PORT}")
    print(f"根目录: {Config.ROOT_DIRECTORY}")
    print("按 Ctrl+C 停止服务")
    
    app.run(
        host=Config.HOST, 
        port=Config.PORT, 
        debug=Config.DEBUG,
        threaded=True  # 支持多线程处理请求
    )