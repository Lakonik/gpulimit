# GPULimit
A simple tool to monitor and limit the power spike of GPU group

## Installation

Notice: Root permission is required to set the power limit or GPU clocks.

```bash
sudo pip3 install git+https://github.com/Lakonik/gpulimit.git
```

## Usage

```bash
$ sudo gpulimit -h
usage: gpulimit [-h] [-i ID] [-o FILE] [-r LOW,HIGH] [-pl POWER] [-lgc LOW,HIGH] [-t TIME] [-rc N] [-swl]

Monitor and limit GPU power peak

optional arguments:
  -h, --help                        show this help message and exit
  -i, --id ID                       GPU index
  -o, --out FILE                    Output log file
  -r, --range LOW,HIGH              Specifies <releaseThreshold, limitThreshold> of maximum power values (e.g. 1500,1700)
  -pl, --power-limit POWER          GPU power cap (w). See nvidia-smi -h for details
  -lgc, --lock-gpu-clocks LOW,HIGH  Specifies <minGpuClock,maxGpuClock>, input can also be a singular desired clock value. See nvidia-smi -h for details
  -t, --time TIME                   Time interval (sec)
  -rc, --release-count N            Number of consecutive steps below the LOW threshold required for the release
  -swl, --start-with-limit          Whether to enforce limit at startup
```