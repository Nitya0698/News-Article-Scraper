from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import sys

class PostInstallCommand(install):
    """Custom post-installation for installation mode."""
    def run(self):
        # Run the standard installation
        install.run(self)
        
        # Run your custom scripts after installation
        print("Running post-installation scripts...")
        
        try:
            # Script 1
            print("Running script 1...")
            subprocess.check_call([sys.executable, "Create_Tracking_Domains_Database.py"])
            print("Table 1 Created successfully\n")
            
            # Script 2
            print("Running script 2...")
            subprocess.check_call([sys.executable, "Create_Articles_Database.py"])
            print("Table 2 created successfully\n")
            
        except subprocess.CalledProcessError as e:
            print(f"Warning: A script failed with error: {e}")
            print("Installation completed but please check the scripts manually.")

setup(
    name="News_Article_Scraper",
    version="1.0.0",
    author="Nitya",
    author_email="sharma.nity@gmail.com",
    description="Dynamically fetching XPATHS, andd self updating them for the best scraping path",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/your-project",
    packages=find_packages(),
    install_requires=[
        "requests",
        "tldextract",
        "lxml",
        "python-dateutil",
        "beautifulsoup4",
        "openai",
        "python-dotenv",
        "rake-nltk",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    cmdclass={
        'install': PostInstallCommand,
    },
    include_package_data=True,
)