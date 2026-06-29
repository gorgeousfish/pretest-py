"""Sphinx configuration for pretest-py documentation."""

import os
import sys

# 添加源代码路径
sys.path.insert(0, os.path.abspath("../src"))

project = "pretest"
copyright = "2026, Xuanyu Cai, Wenli Xu"
author = "Xuanyu Cai, Wenli Xu"
version = "0.1.0"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

# Napoleon 配置（NumPy 风格）
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_keyword = True
napoleon_preprocess_types = True

# Autodoc 配置
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

# MyST（Markdown 支持）
myst_enable_extensions = ["colon_fence", "dollarmath"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

# 主题
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "prev_next_buttons_location": "bottom",
    "style_nav_header_background": "#2980B9",
    "navigation_depth": 4,
}

# Intersphinx 外部链接
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# 排除
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
