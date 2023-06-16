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

### Rokoko Device
put device folder into devices folder, my path for that is C:\Program Files\Epic Games\UE_5.1\Engine\Plugins\VirtualProduction\Switchboard\Source\Switchboard\switchboard\devices

### OBS Device
1 - put obs folder into devices https://drive.google.com/file/d/1SkIdi4BZRiVvZt_tHLAzMY1vjof8PPLh/view?usp=share_link

my path for devices - C:\Program Files\Epic Games\UE_5.1\Engine\Plugins\VirtualProduction\Switchboard\Source\Switchboard\switchboard\devices

2 - add simpleobsws and websockets libraries into switchboard python site-packages - C:\Program Files\Epic Games\UE_5.1\Engine\Extras\ThirdPartyNotUE\SwitchboardThirdParty\Python\Lib\site-packages
