# cisco-catalyst-sdwan-client-async
Python AsyncIO client for Cisco Catalyst SDWAN 20.6.x 20.9.x 20.12.x


# Installation

This client comes with a minimal set of requirements:

```python
pip install asyncio
pip install httpx
pip install ipaddress
```

# Basic usage

```python
# create session
session = Vmanage(host=host, username=username, password=password)

# fetch device inventory (controllers and vedges)
devices = await session.get_devices()
for k,v in devices.item():
  print(f'DeviceID {k} with hostname {v.hostname}')

# fetch interfaces data for a specific device
device = devices[some_device_id]
interfaces = await session.get_device_interfaces(device)

# fetch TLOC data for a specific device
device = devices[some_device_id]
tlocs = await session.get_device_tlocs(device)

# fetch template values for a specific device
device = devices[some_device_id]
values = await session.get_device_template_values(device)

# request another API endpoint using GET
health_data = await session.get('/health/devices',params={'site_id':'1234'})

# ... or using POST
clear_alarm = await session.post('/alarms/clear',data={'alarm_uuid':'29f9bf31-0fbe-4114-b8f0-e6234699485c'})
```

# Advanced usage

Use 'get_all()' method to run concurent tasks under semaphore control:

```python
session = Vmanage(host=host, username=username, password=password, semaphore=50)
devices = await session.get_devices()

tasks = [session.get_device_tlocs(device) for device in devices]
tlocs = await session.get_all(tasks)
```
