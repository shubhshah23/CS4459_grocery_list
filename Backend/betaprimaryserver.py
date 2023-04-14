import grpc
from concurrent import futures
from typing import Dict, List
import time
import threading
from queue import Queue
from queue import Empty


import list_pb2
import list_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

def flip_bool_by_string(lst, string):
    for i, pair in enumerate(lst):
        if pair[0] == string:
            lst[i] = (pair[0], not pair[1])
            return lst
    return None  # If no match found

class ListService(list_pb2_grpc.ListServiceServicer):
    def __init__(self):
        self.lists: Dict[(str, str), List[(str, bool)]] = {}
        self.subscriptions: Dict[(str, str), List[grpc.ServicerContext]] = {}
        self.lock = threading.Lock()

    def JoinGroup(self, request: list_pb2.GroupRequest, context: grpc.ServicerContext) -> list_pb2.GroupResponse:
        print("Joining Group")
        with self.lock:
            if (request.name, request.password) in self.lists:
                # The group exists
                self.sendGroupRequestsToBackup("JoinGroup", request.name, request.password)
                return list_pb2.GroupResponse(success=True)
            else:
                # The group doesn't exist
                return list_pb2.GroupResponse(success=False)
        
    def CreateGroup(self, request: list_pb2.GroupRequest, context: grpc.ServicerContext) -> list_pb2.GroupResponse:
        with self.lock: 
            if (request.name, request.password) in self.lists:
                # The group already exists
                return list_pb2.GroupResponse(success=False)
            else:
                # Create the group with an empty list
                self.lists[(request.name, request.password)] = []
                self.sendGroupRequestsToBackup("CreateGroup", request.name, request.password)
                print("\n Creating group {request.name} with password {request.password}")
                return list_pb2.GroupResponse(success=True)
            
    def sendItemRequestsToBackup(self, operation, group, password, item):
        connectionString = 'localhost:' + str(9000)     
        with grpc.insecure_channel(connectionString) as channel:
            stub = list_pb2_grpc.ListServiceStub(channel) 

            if (operation == 'AddItem'):
                response = stub.AddItem(list_pb2.ItemRequest(group=group, password=password, item=item))
                print("\n Backup Server Response: Add Item:", response)
            elif (operation == "CheckItem"):
                response = stub.CheckItem(list_pb2.ItemRequest(group=group, password=password, item=item))
                print("\n Backup Server Response: Check Item:", response)
            elif (operation == "DeleteItem"):
                response = stub.DeleteItem(list_pb2.ItemRequest(group=group, password=password, item=item))
                print("\n Backup Server Response: Delete Item:", response)
         
            
    def sendGroupRequestsToBackup(self, operation, group_name, group_password):
        connectionString = 'localhost:' + str(9000)     
        with grpc.insecure_channel(connectionString) as channel:
            stub = list_pb2_grpc.ListServiceStub(channel) 

            if (operation == "CreateGroup"):
                response = stub.CreateGroup(list_pb2.GroupRequest(name=group_name, password=group_password))
                print("\n Backup Server Response: Creating group", response)
            elif (operation == "JoinGroup"):
                response = stub.JoinGroup(list_pb2.GroupRequest(name=group_name, password=group_password))
                print("\n Backup Server Response: Creating group:", response)

    def AddItem(self, request: list_pb2.ItemRequest, context: grpc.ServicerContext) -> list_pb2.ItemResponse:
        group = request.group
        password = request.password
        item = request.item

        if (group, password) not in self.lists:
            self.lists[(group, password)] = []

        self.lists[(group, password)].append((item, False))
        print(f"{item} added to group {group}, {password}")

        response = list_pb2.ItemResponse(success=True)
        self.sendItemRequestsToBackup("AddItem", group, password, item)
        print("\n pdated List", self.lists)

        self._notify_clients(group, password, list_pb2.Update(type=list_pb2.Update.ADD, item=item))


        
        return response

    def CheckItem(self, request: list_pb2.ItemRequest, context: grpc.ServicerContext) -> list_pb2.ItemResponse:
        group = request.group
        password = request.password
        item = request.item

        if (group, password) not in self.lists:
            self.lists[(group, password)] = []

        if(flip_bool_by_string(self.lists[(group, password)], item)):
            success=True 
            self._notify_clients(group, password, list_pb2.Update(type=list_pb2.Update.CHECK, item=item))
        else:
            success=False
        
        print(f"{item} check on group {group}, {password}")

        response = list_pb2.ItemResponse(success=success)
        self.sendItemRequestsToBackup("CheckItem", group, password, item)
        print("\n Updated List", self.lists)

        
        return response



    def GetItems(self, request: list_pb2.ItemsRequest, context: grpc.ServicerContext) -> list_pb2.ItemsResponse:
        group = request.group
        password = request.password

        if (group, password) not in self.lists:
            return list_pb2.ItemsResponse(items=None)

        items = self.lists[(group, password)]
        formatted_items = []

        for item in items:
            formatted_item = list_pb2.Item(name=item[0], checked=item[1])
            formatted_items.append(formatted_item)

        response = list_pb2.ItemsResponse(items=formatted_items)
        return response

    def DeleteItem(self, request: list_pb2.ItemRequest, context: grpc.ServicerContext) -> list_pb2.ItemResponse:
        group = request.group
        password = request.password
        item = request.item

        if (group, password) not in self.lists:
            self.lists[(group, password)] = []
            self.clients[(group, password)] = []

        if ((item, True)) in self.lists[(group, password)] or ((item, False)) in self.lists[(group, password)]:
            try:
                self.lists[(group, password)].remove((item, False))
            except ValueError:
                pass  # item not found, do nothing
            try:
                self.lists[(group, password)].remove((item, True))
            except ValueError:
                pass  # item not found, do nothing
            
            print(f"{item} removed from group {group}, {password}")
            response = list_pb2.ItemResponse(success=True)
            self.sendItemRequestsToBackup("DeleteItem", group, password, item)
            print("primarserver list", self.lists)


        else:
            print(f"{item} not found in group {group}, {password}")
            response = list_pb2.ItemResponse(success=False)

        if response.success:
            self._notify_clients(group, password, list_pb2.Update(type=list_pb2.Update.DELETE, item=item))
        return response

    def SubscribeToUpdates(self, request: list_pb2.SubscribeRequest, context: grpc.ServicerContext):
        group = request.group
        password = request.password
        client_queue = Queue()
    
        with self.lock:
            if (group, password) not in self.subscriptions:
                self.subscriptions[(group, password)] = []
            self.subscriptions[(group, password)].append(client_queue)
    
        try:
            while context.is_active():
                try:
                    update = client_queue.get(timeout=1)
                    yield update  # Use the yield statement here
                except Empty:
                    pass
        finally:
            with self.lock:
                self.subscriptions[(group, password)].remove(client_queue)

    def _notify_clients(self, group: str, password: str, update: list_pb2.Update):
        #print(self.lists)
        with self.lock:
             if (group, password) in self.subscriptions:
                for client_queue in self.subscriptions[(group, password)]:
                    client_queue.put(update)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    list_pb2_grpc.add_ListServiceServicer_to_server(ListService(), server)
    server.add_insecure_port('[::]:50058')
    server.start()
    print("Server started listening on port 50058")
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()