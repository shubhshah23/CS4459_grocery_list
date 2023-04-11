import grpc
from concurrent import futures
from typing import Dict, List
import time

import list_pb2
import list_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ListService(list_pb2_grpc.ListServiceServicer):
    def __init__(self):
        self.lists: Dict[str, List[str]] = {}

    def AddItem(self, request: list_pb2.ItemRequest, context: grpc.ServicerContext) -> list_pb2.ItemResponse:
        group = request.group
        item = request.item

        if group not in self.lists:
            self.lists[group] = []

        self.lists[group].append(item)
        print(f"{item} added to group {group}")

        response = list_pb2.ItemResponse(success=True)
        return response

    def GetItems(self, request: list_pb2.ItemsRequest, context: grpc.ServicerContext) -> list_pb2.ItemsResponse:
        group = request.group

        if group not in self.lists:
            self.lists[group] = []

        items = self.lists[group]

        response = list_pb2.ItemsResponse(items=items)
        return response

    def DeleteItem(self, request: list_pb2.ItemRequest, context: grpc.ServicerContext) -> list_pb2.ItemResponse:
        group = request.group
        item = request.item

        if group not in self.lists:
            self.lists[group] = []
            self.clients[group] = []

        if item in self.lists[group]:
            self.lists[group].remove(item)
            print(f"{item} removed from group {group}")
            response = list_pb2.ItemResponse(success=True)
        else:
            print(f"{item} not found in group {group}")
            response = list_pb2.ItemResponse(success=False)

        return response

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
