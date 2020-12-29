import setuptools


setuptools.setup(
    name="simple_blog_generator",
    version="0.1",
    description="A super basic static site generator for blogs",
    python_requires=">=3.6",
    packages=setuptools.find_packages(),
    package_data={"": ["themes/*/static/*","themes/*/templates/*.html"]},
    scripts=["generate_blog"],
    install_requires=["wheel", "jinja2", "markdown"],
    classifiers=["Intended Audience :: Developers",
                 "Natural Language :: English"
                 "Operating System :: OS Independent",
                 "Programming Language :: Python :: 3.6"],
    keywords="static blog website jinja2"
)
