rm -r ./output/**

rm -r ./train/dataset/cache
rm -r ./train/dataset/target
rm -r ./train/edit-dataset/cache
rm -r ./train/edit-dataset/control
rm -r ./train/edit-dataset/target

mkdir -p ./train/dataset/target
mkdir -p ./train/dataset/cache
mkdir -p ./train/edit-dataset/cache
mkdir -p ./train/edit-dataset/control
mkdir -p ./train/edit-dataset/target