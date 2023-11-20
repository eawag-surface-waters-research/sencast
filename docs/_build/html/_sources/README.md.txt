# Sencast Documentation

Sencast uses [Sphinx](https://www.sphinx-doc.org/en/master/index.html) to auto generate its documentation. 

## Updating Documentation

1. Make changes to the .rst files
2. Install the sphinx conda environment
```
conda env create -f ~/sencast/docs/environment.yml
```
3. Rebuild the html docs
```
conda activate sphinx
cd sencast/docs
make html
```
4. Push the changes to the gitlab remote repository