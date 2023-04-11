import grpc

import list_pb2
import list_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:50058') as channel:
        stub = list_pb2_grpc.ListServiceStub(channel)

        group = "group1"
        item = "item2"

        response = stub.AddItem(list_pb2.ItemRequest(group=group, item=item))
        print("AddItem response:", response)

        response = stub.GetItems(list_pb2.ItemsRequest(group=group))
        print("GetItems response:", response)

        # Delete the item
        response = stub.DeleteItem(list_pb2.ItemRequest(group=group, item=item))
        print("DeleteItem response:", response)

if __name__ == '__main__':
    run()
