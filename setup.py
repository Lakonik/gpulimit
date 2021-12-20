from setuptools import setup


setup(name='gpulimit',
      version='0.1',
      description='A simple tool to monitor and limit the power spike of gpu group',
      author='Hansheng Chen',
      author_email='hanshengchen97@gmail.com',
      entry_points={'console_scripts': ['gpulimit=gpulimit:main']},
      install_requires=[
        "numpy"
      ],
      python_requires='>=3.5, <4',
      )
