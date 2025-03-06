#!/usr/bin/python3
"""
Cisco Catalyst SDWAN Async Client
Tested on 20.6.4 / 20.9.4 / 20.12.4
"""
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import asyncio
import httpx
import json
from ipaddress import IPv4Address, IPv4Network, AddressValueError
import nest_asyncio
nest_asyncio.apply()

# CLASS Device
@dataclass
class DeviceData:
    uuid:str
    persona:str
    system_ip:IPv4Address|None
    hostname:str|None
    site_id:int|None
    model:str|None
    version:str|None
    template_id:str|None
    template_name:str|None
    is_managed: bool
    is_valid:bool
    is_sync:bool
    is_reachable:bool
    raw_data:Dict
    latitude:float=0
    longitude:float=0

# CLASS Interface
@dataclass
class InterfaceData:
    if_name: str
    if_desc:str
    if_type:str
    if_mac:str
    vpn_id:str
    ip:IPv4Address
    network:IPv4Network
    raw_data:Dict

# CLASS Virtual_IP
@dataclass
class VrrpData:
    if_name: str
    group: int
    priority: int
    preempt: bool
    master: bool
    ip:IPv4Address
    raw_data:Dict

# CLASS TLOC
@dataclass
class TlocData:
    site_id: int
    system_ip: IPv4Address
    private_ip: IPv4Address
    public_ip: IPv4Address
    preference: int
    weight: int
    encapsulation: str
    color:str
    raw_data:Dict

# Class definition
class Vmanage:
    # Class constructor
    def __init__(self, host:str, username:str , password:str , verify:bool=False, port:int=443, semaphore:int=40, debug:bool=False):
        # Base properties
        self.base_url = 'https://' + host + ":" + str(port)
        self.semaphore = semaphore
        # SSL verify
        self.verify = verify
        # Login
        self.connected = self.__login(username,password)
        if self.connected:
            self.session = httpx.AsyncClient(verify=verify)

    # Login method
    def __login(self, username:str, password:str) -> bool:
        """
        Authenticates to vManage and update session
        """
        # Create HTTPX client
        client = httpx.Client(verify=self.verify)
        # Submit login form
        headers = { "Content-Type": "application/x-www-form-urlencoded" }
        data = { "j_username": f"{username}", "j_password": f"{password}" }
        try:
            response = client.post(f"{self.base_url}/j_security_check", data=data, headers=headers)
        except httpx.HTTPError as e:
            raise ConnectionError(f'ConnectionError: {e}')
        # Login OK when response code is 200 AND content is not HTML
        if response.status_code == 200 and not response.text.startswith('<html>'):
            # Get session cookie
            cookie = response.headers.get('Set-Cookie').split(";")[0]
            # Set headers
            self.headers = {
                "Content-Type": "application/json",
                "Cookie" : cookie
            }
            # Get CSRF token
            try:
                response = client.get(f"{self.base_url}/dataservice/client/token", headers=self.headers)
            except httpx.HTTPError as e:
                raise ConnectionError(f'ConnectionError: {e}')    
            if response.status_code == 200:
                # Add CSRF header
                self.headers["X-XSRF-TOKEN"] = response.text
                # Update base path
                self.base_url = self.base_url + "/dataservice"
                return True
        # Fail by default
        return False

    # Private method
    async def __get(self,path:str,params:dict={}) -> str:
        """
        Generic GET request
        """
        if not self.connected:
            return None
        try:
            response = await self.session.get(f"{self.base_url}{path}", headers=self.headers, params=params, timeout=None)
        except httpx.HTTPError as e:
            raise ConnectionError(f'ConnectionError: {e}')
        return response.text if response.status_code == 200 else None

    # Private method
    async def __post(self,path:str,params:dict={},data:dict={}) -> str:
        """
        Generic POST request
        """
        if not self.connected:
            return None
        try:
            response = await self.session.post(f"{self.base_url}{path}", headers=self.headers, params=params, data=json.dumps(data),timeout=None)
        except httpx.HTTPError as e:
            raise ConnectionError(f'ConnectionError: {e}')
        return response.text if response.status_code == 200 else None

    # Public method
    async def get(self,endpoint:str,params:dict={}) -> dict:
        response = await self.__get(endpoint,params=params)
        return json.loads(response)['data'] if response and 'data' in response else None

    # Public method
    async def post(self,endpoint:str,params:dict={},data:dict={}) -> dict:
        response = await self.__post(endpoint,params=params,data=data)
        return json.loads(response)['data'] if response else None

    # Concurrent GET
    async def get_all(self,tasks) -> list[any]:
        semaphore = asyncio.Semaphore(self.semaphore)
        async def sem_task(task):
            async with semaphore:
                return await task
        return await asyncio.gather(*[sem_task(task) for task in tasks])

    # Get devices
    async def get_devices(self)->Dict[str,DeviceData]:
        # Fetch raw data
        tasks = [self.get(f"/system/device/controllers"), self.get(f"/system/device/vedges"), self.get("/device")]
        results = await self.get_all(tasks)

        # Prepare data
        controllers = { e["uuid"]: e for e in results[0] }
        vedges = { e["uuid"]: e for e in results[1] }
        statuses = { e["uuid"]: e for e in results[2] }

        # merge data
        merged = controllers | vedges
        for e in merged:
            if e in statuses:
                merged[e] = merged[e] | statuses[e]

        # parse merged data
        devices = {}
        for i, (k,v) in enumerate(merged.items()):
            devices[v["uuid"]] = DeviceData(
                uuid=v["uuid"],
                persona=v["personality"],
                system_ip=IPv4Address(v["system-ip"]) if ("system-ip" in v) else None,
                hostname=v["host-name"] if ("host-name" in v) else None,
                site_id=v["site-id"] if ("site-id" in v) else None,
                model=v["deviceModel"].replace("vedge-", "").replace("cloud", "vbond") if "deviceModel" in v else None,
                version=v["version"] if "version" in v else None,
                template_id=v["templateId"] if "templateId" in v else None,
                template_name=v["template"] if "template" in v else None,
                is_managed=True if (("managed-by" in v) and (v["managed-by"] != "Unmanaged")) else False,
                is_valid=True if (v["validity"] == "valid") else False,
                is_sync=True if "configStatusMessage" in v and v["configStatusMessage"]=="In Sync" else False,
                is_reachable=True if "reachability" in v and v["reachability"]=="reachable" else False,
                latitude=v["latitude"] if ("latitude" in v) else 0.0,
                longitude=v["longitude"] if ("longitude" in v) else 0.0,
                raw_data=v
            )
        return devices

    # Get device interfaces
    async def get_device_interfaces(self,device:DeviceData)->List[InterfaceData]:
        raw_data = await self.get("/device/interface/synced",{"deviceId":device.system_ip})
        if not raw_data:
            return None
        parsed_interfaces = []
        for raw_interface in raw_data:
            parsed_interfaces.append(
                    InterfaceData(
                    if_name  = raw_interface["ifname"],
                    if_desc  = raw_interface.get("description","N/A"),
                    if_type  = raw_interface["interface-type"],
                    if_mac   = raw_interface["hwaddr"],
                    vpn_id   = raw_interface["vpn-id"],
                    ip       = IPv4Address(raw_interface["ip-address"]),
                    network  = IPv4Network(f'{raw_interface["ip-address"]}/{raw_interface["ipv4-subnet-mask"]}',strict=False),
                    raw_data = raw_interface
                )
            )
        return parsed_interfaces

    # Get device TLOCs
    async def get_device_tlocs(self,device:DeviceData)->List[TlocData]:
        raw_data = await self.get("/device/omp/tlocs/advertised",{"deviceId":device.system_ip})
        if not raw_data:
            return None
        tlocs = []
        for tloc in raw_data:
            tlocs.append(
                TlocData(
                    site_id=tloc["site-id"],
                    system_ip=IPv4Address(tloc["ip"]),
                    private_ip=IPv4Address(tloc["tloc-private-ip"]),
                    public_ip=IPv4Address(tloc["tloc-public-ip"]),
                    preference=tloc["preference"],
                    weight=tloc["weight"],
                    encapsulation=tloc["encap"],
                    color=tloc["color"].lower(),
                    raw_data=tloc
                )
            )
        return tlocs 

    # Get device VRRP info
    async def get_device_vrrp(self,device:DeviceData)->List[VrrpData]:
        raw_data = await self.get("/device/vrrp",{"deviceId":device.system_ip})
        #print(raw_data)
        if not raw_data:
            return None
        vips = []
        for vip in raw_data:
            if (vip["vrrp-state"] == "proto-state-master"):
                master = True
            else:
                master = False
            vips.append(
                VrrpData(
                    if_name=vip["if-name"],
                    ip=IPv4Address(vip["virtual-ip"]),
                    group=vip["group-id"],
                    priority=vip["priority"],
                    preempt=vip["preempt"],
                    master=master,
                    raw_data=vip
                )
            )
        return vips

    # Get device template values
    async def get_device_template_values(self,device:DeviceData)->Dict:
        if not device.uuid or not device.template_id:
            return None
        payload = {
            "templateId": device.template_id,
            "deviceIds": [device.uuid],
            "isEdited": False,
            "isMasterEdited": False
        }
        raw_data = await self.post("/template/device/config/input",{},payload)
        #print(raw_data)
        try:
            return raw_data[0]
        except:
            return None
