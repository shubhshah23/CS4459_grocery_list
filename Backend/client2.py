import grpc
import threading

import list_pb2
import list_pb2_grpc

def receive_updates(stub, group, password):
    for update in stub.SubscribeToUpdates(list_pb2.SubscribeRequest(group=group, password=password)):
        if update.type == list_pb2.Update.ADD:
            print(f"Added item '{update.item}'")
        elif update.type == list_pb2.Update.DELETE:
            print(f"Deleted item '{update.item}'")
        elif update.type == list_pb2.Update.CHECK:
            print(f"Checked item '{update.item}'")

def run():
    with grpc.insecure_channel('localhost:50058') as channel:
        stub = list_pb2_grpc.ListServiceStub(channel)

        group = "group1"
        password = "123"
        item = "item2"

        # Start the receive_updates thread
        thread = threading.Thread(target=receive_updates, args=(stub, group, password))
        thread.start()

        response = stub.AddItem(list_pb2.ItemRequest(group=group, password=password, item=item))
        print("AddItem response:", response)

        response = stub.GetItems(list_pb2.ItemsRequest(group=group, password=password))
        print("GetItems response:", response)

        response = stub.CheckItem(list_pb2.ItemRequest(group=group, password=password, item=item))
        print("CheckItem response:", response)

        # Delete the item
        response = stub.DeleteItem(list_pb2.ItemRequest(group=group, password=password, item=item))
        print("DeleteItem response:", response.success)

        # Wait for the receive_updates thread to finish
        thread.join()

      

if __name__ == '__main__':
    run()
