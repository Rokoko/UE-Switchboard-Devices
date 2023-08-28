# UE Switchboard Devices

UE Switchboard is a Python tool that comes with Unreal Engine. It is primarily used for nDisplay synchronization, but it can also be used for synchronized recording across different devices from manufacturers such as Vicon, xSens, and Optitrack. Additionally, it can be used for recording UE scenes or live-action facial captures.

![ue switchboard with devices](https://github.com/Rokoko/UE-Switchboard-Devices/blob/main/images/image.png)

Rokoko Device has two implementations:
- Trigger messages device - this is a production ready, low latency, industry aligned way of doing a synced recording
- Command API Device - this is a way based on http post requests, compatible with Studio Legacy
  
The OBS device that could be useful if you want to make a recording of audio and video references.

## Demo Video
In the video I'm demonstrating a use of two new devices for UE Switchboard - Rokoko Studio and OBS. Also I'm showing how to do a sync recording.


Video - https://drive.google.com/file/d/1lWspsHGplYHJ3_2MyrYa8TdDLNpkFnzL/view?usp=sharing

## How to Install

1 - Make a new UE project from template "Virtual Production / nDisplay". When Editor started, you should have a new button in the main toolbar to run the switchboard. First click on it will launch the installation process.

Then close the switch board window.

2 - Put devices script folders (rokoko and obs) into devices folder, that have to be located on your UE installation path
For instance, C:\Program Files\Epic Games\UE_5.1\Engine\Plugins\VirtualProduction\Switchboard\Source\Switchboard\switchboard\devices

2 - Locate the SwitchboardThirdParty folder in your installed UE
For instance, C:\Program Files\Epic Games\UE_5.1\Engine\Extras\ThirdPartyNotUE\SwitchboardThirdParty

In the folder you should modify requirements.txt and add there 2 lines
```
simpleobsws>=v1.0.0
websockets==10.4
```

3 - remove the sub-folder Scripts inside the SwitchboardThirdParty\Python

4 - launch the switchboard again from UE or from installed shortcut. New required libraries have to be added and new Rokoko and OBS devices should be able to start.
