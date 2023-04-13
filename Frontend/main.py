from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem, TabbedPanelHeader
from kivy.uix.anchorlayout import AnchorLayout
from kivy.metrics import sp
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.properties import BooleanProperty
from kivy.uix.widget import Widget
from kivy.config import Config

import grpc
import threading

import list_pb2
import list_pb2_grpc

def receive_updates(stop_event):
    global group_name
    global group_pass

    if group_name and group_pass:
        subscribe_request = list_pb2.SubscribeRequest(group=group_name, password=group_pass)
        for update in stub.SubscribeToUpdates(subscribe_request):
            if update.type == list_pb2.Update.ADD:
                global_list_container.add_item(None, update.item)
            elif update.type == list_pb2.Update.DELETE:
                global_list_container.remove_item(None, update.item)
            elif update.type == list_pb2.Update.CHECK:
                print(f"Toggled item '{update.item}'")
                global_list_container.update_checkbox(None, update.item)
                
            print(f"Received update: {update.type}, {update.item}")

            if stop_event.is_set():
                break
    else:
        print("You must join or create a group before subscribing to updates.")


class CustomCheckBox(ToggleButton):
    image_source = StringProperty('unchecked.png')
    user_triggered = BooleanProperty(False)
    server_triggered = BooleanProperty(False)


    def __init__(self, stub, group_name, group_pass, **kwargs):
        super(CustomCheckBox, self).__init__(**kwargs)
        self.stub = stub
        self.group_name = group_name
        user_triggered = BooleanProperty(False)
        self.group_pass = group_pass
        self.background_normal = ''
        self.background_down = ''
        self.background_color = [0, 0, 0, 0]  # set the background color to transparent
        #self.bind(state=self.on_state)
        self.bind(pos=self.update_rect, size=self.update_rect)

        Clock.schedule_once(self.create_image, 0)  # Add this line to schedule the image creation

    def create_image(self, *args):
        with self.canvas.before:
            Color(1, 1, 1, 1)
            size = 56  # Set the size of the square
            self.rect = Rectangle(source=self.image_source,
                                  size=(size, size),
                                  pos=(self.parent.x + 10, int(self.center_y - size/2)), 
                                  allow_stretch=True,
                                  keep_ratio=True)
            
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.user_triggered = True
            if self.state == 'down':
                self.state = 'normal'
            else:
                self.state = 'down'

            if self.parent:
                item_text = self.parent.children[1].text
                response = self.stub.CheckItem(list_pb2.ItemRequest(group=self.group_name, password=self.group_pass, item=item_text))
                print("CheckItem response:", response.success)
        return super(CustomCheckBox, self).on_touch_down(touch)


    def update_rect(self, *args):
        size = 56  # Set the size of the square
        self.rect.pos = (self.parent.x + 10, int(self.center_y - size/2))


class RoundedButton(Button):
    def __init__(self, button_color=(0.541, 0.769, 0.290, 1), text_color=(1, 1, 1, 1), font_size=24, **kwargs):
        super(RoundedButton, self).__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.border_color = (0, 0, 0, 1)
        self.corner_radius = 20
        self.border_width = 2
        self.font_size = font_size
        self.button_color = button_color
        self.color = text_color

        with self.canvas.before:
            Color(rgba=self.button_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.corner_radius, ])
            Color(rgba=self.border_color)
            Line(width=self.border_width, rounded_rectangle=[self.x, self.y, self.width, self.height, self.corner_radius])

        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(rgba=self.button_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[self.corner_radius, ])
            Color(rgba=self.border_color)
            Line(width=self.border_width, rounded_rectangle=[self.x, self.y, self.width, self.height, self.corner_radius])


class ListContainer(BoxLayout):
    def __init__(self, **kwargs):
        super(ListContainer, self).__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = 0
        self.padding = (10, 70, 10, 10)

        with self.canvas.before:
            Color(0.298, 0.498, 0.957, 1) # Set the background color to light blue
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self.update_rect, pos=self.update_rect)

        self.scroll_list = BoxLayout(orientation='vertical', size_hint_y=None)
        self.scroll_list.bind(minimum_height=self.scroll_list.setter('height'))
        scroll_view = ScrollView(size_hint=(1, 1), bar_width=10)
        scroll_view.add_widget(self.scroll_list)
        self.add_widget(scroll_view)

        input_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.add_widget(input_box)

        self.input_text = TextInput(multiline=False, hint_text='Enter item', size_hint_x=0.75, font_size=30)
        input_box.add_widget(self.input_text)

        add_button = RoundedButton(text='Add',
                                    size_hint_x=0.25,
                                    bold=True,
                                    font_size=28,
                                    button_color=(0.541, 0.769, 0.290, 1),
                                    text_color=(1, 1, 1, 1))
        add_button.bind(on_press=self.add_item_on_server)
        input_box.add_widget(add_button)
        add_button.border = (4, 4, 4, 4)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def add_item_on_server(self, instance):
        item_text = self.input_text.text
        if item_text:
            response = stub.AddItem(list_pb2.ItemRequest(group=group_name, password=group_pass, item=item_text))
            print("AddItem response:", response)

    def add_item(self, instance, item_text):
        # Use Clock.schedule_once to schedule the creation of the item on the main thread
        Clock.schedule_once(lambda dt: self.create_item(item_text), 0)

    def create_item(self, item_text, checked=False):
        item = BoxLayout(size_hint_y=None, height=100, spacing=12)
        # Create a BoxLayout for the checkbox, label, and button
        content = BoxLayout(size_hint_x=0.8, spacing=12)
        checkbox = CustomCheckBox(stub=stub, group_name=group_name, group_pass=group_pass, size_hint_x=None, width=56)
        if checked:
            checkbox.state = 'down'
            checkbox.image_source = 'checked.png'
        content.add_widget(checkbox)
        label = Label(text=item_text, font_size=32, color=(0, 0, 0, 1), valign='middle', halign='left')
        label.bind(width=lambda *x: label.setter('text_size')(label, (label.width, None)))
        content.add_widget(label)
        # Add a transparent BoxLayout for vertical alignment
        transparent_layout = BoxLayout(size_hint_x=0.4, orientation="vertical")
        transparent_layout.add_widget(Widget())
        remove_button = RoundedButton(text='Remove',
                                      size_hint=(1, 1),
                                      button_color=(1, 0, 0, 1),  # Set the button color to red
                                      text_color=(1, 1, 1, 1))
        remove_button.bind(on_press=self.remove_item_on_server)
        transparent_layout.add_widget(remove_button)
        transparent_layout.add_widget(Widget())
        content.add_widget(transparent_layout)
        # Add the content BoxLayout to the item BoxLayout
        item.add_widget(content)
        # Store a reference to the CustomCheckBox widget in the item BoxLayout
        item.checkbox = checkbox
        self.scroll_list.add_widget(item)
        self.input_text.text = ""
        # Schedule the creation of the checkbox image with a delay
        Clock.schedule_once(lambda dt: checkbox.create_image(), 0.1)
        # Set the 'item' as a property of remove_button to access it in the remove_item function
        remove_button.item = item

    def remove_item_on_server(self, instance):
        item_layout = instance.item
        item_label = item_layout.children[0].children[1]  # get the label widget
        item_text = item_label.text
        print(f"tryna remove item {item_text}")
        response = stub.DeleteItem(list_pb2.ItemRequest(group=group_name, password=group_pass, item=item_text))
        print("DeleteItem response:", response.success)


    def remove_item(self, instance, item_text):
        # Use Clock.schedule_once to schedule the deletion of the item on the main thread
        Clock.schedule_once(lambda dt: self.delete_item(item_text), 0)

    def delete_item(self, item_text):
        # Iterate over each child of the scroll_list
        for child in self.scroll_list.children:
            # Get the label widget of the child
            label = child.children[0].children[1]
            # Check if the text of the label matches the item_text
            if label.text == item_text:
                # Remove the child from the scroll_list
                self.scroll_list.remove_widget(child)
                break

    def update_checkbox(self, instance, item_text):
        # Use Clock.schedule_once to schedule flipping the 'checked' of the item on the main thread
        Clock.schedule_once(lambda dt: self.flip_checkbox(item_text), 0)

    def flip_checkbox(self, item_text):
        print("called flip")
    
        for child in self.scroll_list.children:
            content = child.children[0]
            label = content.children[1]
            checkbox = content.children[2]
            print(f"Found checkbox with state: {checkbox.state}")  # Add this line
    
            if label.text == item_text:
                if checkbox.state == 'down':
                    checkbox.image_source = 'unchecked.png'
                    checkbox.state = 'normal'
                else:
                    checkbox.image_source = 'checked.png'
                    checkbox.state = 'down'
    
                checkbox.rect.source = checkbox.image_source
                break

    def clear_items(self):
        # Remove all widgets from the scroll_list
        for widget in self.scroll_list.children:
            print(repr(widget))
        self.scroll_list.clear_widgets()
        

class ListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.list_container = ListContainer()
        self.add_widget(self.list_container)

        manage_group_button = RoundedButton(text="Manage Group",
                                    pos_hint={'right': 0.98, 'top': 0.98},
                                    size_hint=(0.46, 0.08),
                                    font_size=30,
                                    bold=True,
                                    button_color=(0.9725, 0.7333, 0.8157, 1),
                                    text_color=(0, 0, 0, 1))
        manage_group_button.bind(on_press=self.switch_to_group_screen)
        self.add_widget(manage_group_button)

    def switch_to_group_screen(self, *args):
        self.manager.current = "group_screen"


class CustomTabbedPanel(TabbedPanel):
    def __init__(self, **kwargs):
        super(CustomTabbedPanel, self).__init__(**kwargs)
        self.default_tab_class = CustomTabbedPanelItem
        self.background_color = (0, 0, 0, 0)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.298, 0.498, 0.957, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    def on_tab_switch(self, instance, tab):
        tab.select()


class CustomTabbedPanelItem(TabbedPanelItem):
    def __init__(self, content=None, is_selected=False, **kwargs):
        super(CustomTabbedPanelItem, self).__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_down = ''
        self.background_normal = ''
        self.color = (0, 0, 0, 1)
        self.state = 'down' if is_selected else 'normal'
        self.canvas.before.clear()
        with self.canvas.before:
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[10,])
            self.bind(pos=self.update_rect, size=self.update_rect)

        # Bind switching of tabs to updating button color
        self.bind(state=self.update_background)

    def update_background(self, instance, value):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.state == 'normal':
                Color(1, 1, 1, 1)
            else:
                Color(0.541, 0.769, 0.290, 1)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[10,])

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    

class GroupScreen(Screen):
    def __init__(self, **kwargs):
        super(GroupScreen, self).__init__(**kwargs)
        with self.canvas.before:
            Color(0.298, 0.498, 0.957, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self.update_rect, pos=self.update_rect)
        
        # Create a CustomTabbedPanel
        tab_panel = CustomTabbedPanel(do_default_tab=False,
                                      pos_hint={'bottom': 0.05},
                                      size_hint=(1, 0.9),
                                      tab_pos='bottom_mid',
                                      tab_width=Window.width / 3)

        # Create three CustomTabbedPanelItem widgets
        tab1 = CustomTabbedPanelItem(text='My Group')
        tab2 = CustomTabbedPanelItem(text='Join Group')
        tab3 = CustomTabbedPanelItem(text='Create Group')
        

        #Set the content of the CustomTabbedPanelItem widgets
        self.my_group_tab = self.my_group_content()
        tab1_content = self.my_group_tab
        tab1.add_widget(tab1_content)
        tab2_content = self.join_group_content()
        tab2.add_widget(tab2_content)
        tab3_content = self.create_group_content()
        tab3.add_widget(tab3_content)

        # Add the CustomTabbedPanelItem widgets to the CustomTabbedPanel
        tab_panel.add_widget(tab1)
        tab_panel.add_widget(tab2)
        tab_panel.add_widget(tab3)

        # Add the CustomTabbedPanel to the GroupScreen
        self.add_widget(tab_panel)
        
        manage_list_button = RoundedButton(text="Manage List",
                                    pos_hint={'right': 0.98, 'top': 0.98},
                                    size_hint=(0.4, 0.08),
                                    font_size=30,
                                    bold=True,
                                    button_color=(0.9686, 0.8627, 0.4353, 1),
                                    text_color=(0, 0, 0, 1))

        manage_list_button.bind(on_press=self.switch_to_list_screen)
        self.label = Label(text="", font_size="20sp", pos_hint={"center_x": 0.5, "center_y": 0.85})
        self.add_widget(self.label)
        self.add_widget(manage_list_button)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def switch_to_list_screen(self, *args):
        if group_name != 'You are not in a group yet' or group_pass != 'You are not in a group yet': 
            self.manager.current = "list_screen"
        else:
            self.show_text(None)

    def show_text(self, instance):
        # Update the label text
        self.label.text = "You must be in a group before you manage a list!"

        # Schedule the label to be cleared after 2 seconds
        Clock.schedule_once(self.clear_label, 2)

    def clear_label(self, dt):
        # Clear the label text
        self.label.text = ""
            
    def update_my_group_content(self):
        # Clear the existing content
        self.my_group_tab.clear_widgets()

        # Add the updated content
        new_content = self.my_group_content()
        self.my_group_tab.add_widget(new_content)

    def my_group_content(self):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10, size_hint=(1, 0.5), pos_hint={'top': 1})

        # Create the first BoxLayout for the first two labels
        first_box = BoxLayout(orientation='vertical', spacing=5)
        first_box.add_widget(Label(text="Group Name:", size_hint_y=None, height=30, font_size=20))
        first_box.add_widget(Label(text=group_name, size_hint_y=None, height=30, font_size=20))

        # Create the second BoxLayout for the last two labels
        second_box = BoxLayout(orientation='vertical', spacing=5)
        second_box.add_widget(Label(text="Group Password:", size_hint_y=None, height=30, font_size=20))
        second_box.add_widget(Label(text=group_pass, size_hint_y=None, height=30, font_size=20))

        # Add the two BoxLayout widgets to the parent layout
        layout.add_widget(first_box)
        layout.add_widget(second_box)

        return layout

    def join_group_content(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        inner_layout = BoxLayout(orientation='vertical',  padding=10, spacing=10)
        inner_layout.add_widget(Label(text="Group Name:", size_hint_y=None, height=40, font_size=20))
        self.join_group_name_input = TextInput(multiline=False, size_hint_y=None, height=40)
        inner_layout.add_widget(self.join_group_name_input)

        inner_layout.add_widget(Label(text="Password:", size_hint_y=None, height=40, font_size=20))
        self.join_group_password_input = TextInput(multiline=False, password=True, size_hint_y=None, height=40)
        inner_layout.add_widget(self.join_group_password_input)


        layout.add_widget(inner_layout)
        layout.add_widget(BoxLayout(size_hint_y=1))  # Add this line to take up remaining space

        join_button = Button(text="Join Group", size_hint_y=None, height=40, font_size=20)
        join_button.bind(on_press=self.join_group)
        layout.add_widget(join_button)
        spacer = Widget(size_hint_y=None, height=90)  # Adjust the height to move the button up or down
        layout.add_widget(spacer)

        return layout

    def create_group_content(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        inner_layout = BoxLayout(orientation='vertical',  padding=10, spacing=10)
        inner_layout.add_widget(Label(text="Group Name:", size_hint_y=None, height=40, font_size=20))
        self.create_group_name_input = TextInput(multiline=False, size_hint_y=None, height=40)
        inner_layout.add_widget(self.create_group_name_input)
        
        inner_layout.add_widget(Label(text="Password:", size_hint_y=None, height=40, font_size=20))
        self.create_group_password_input = TextInput(multiline=False, password=True, size_hint_y=None, height=40)
        inner_layout.add_widget(self.create_group_password_input)

        layout.add_widget(inner_layout)
        layout.add_widget(BoxLayout(size_hint_y=1))  # Add this line to take up remaining space

        create_button = Button(text="Create Group", size_hint_y=None, height=40, font_size=20)
        create_button.bind(on_press=self.create_group)
        layout.add_widget(create_button)
        spacer = Widget(size_hint_y=None, height=90)  # Adjust the height to move the button up or down
        layout.add_widget(spacer)

        return layout
    
    def join_group(self, *args):
        join_group_name = self.join_group_name_input.text
        join_group_password = self.join_group_password_input.text
        response = stub.JoinGroup(list_pb2.GroupRequest(name=join_group_name, password=join_group_password))
        if response.success:
            # Update the group name and password variables
            global group_name
            global group_pass
            group_name = join_group_name
            group_pass = join_group_password

            global group_changed
            group_changed = True
            # Restart thread for receiving updates
            global stop_update_event
            stop_update_event.set()
            stop_update_event.clear()  # Reset the event for the new thread
            threading.Thread(target=receive_updates, args=(stop_update_event,)).start()

            # Get the updated group list from server
            global global_list_container
            global_list_container.clear_items()
            response = stub.GetItems(list_pb2.ItemsRequest(group=group_name, password=group_pass))
            for item in response.items:
                print(item.name, item.checked)
                global_list_container.create_item(item.name, checked=item.checked)  # Call the create_item method with the item name and checked status

            # Update "my group" screen
            self.update_my_group_content()
            print("Join group succeeded", flush=True)
        else:
            print("Join group failed")



    def create_group(self, *args):
        print("test")
        
        create_group_name = self.create_group_name_input.text
        create_group_password = self.create_group_password_input.text
        response = stub.CreateGroup(list_pb2.GroupRequest(name=create_group_name, password=create_group_password))
        if response.success:
            # Update the group name and password variables
            global group_name
            global group_pass
            group_name = create_group_name
            group_pass = create_group_password

            global group_changed
            group_changed = True
            # Restart thread for receiving updates
            global stop_update_event
            stop_update_event.set()
            stop_update_event.clear()  # Reset the event for the new thread
            threading.Thread(target=receive_updates, args=(stop_update_event,)).start()
             # Get the updated group list from server
            global global_list_container
            global_list_container.clear_items()
            response = stub.GetItems(list_pb2.ItemsRequest(group=group_name, password=group_pass))
            for item in response.items:
                print(item.name, item.checked)
                global_list_container.create_item(item.name, checked=item.checked)  # Call the create_item method with the item name and checked status

            # Update "my group" screen
            self.update_my_group_content()
            print("Create group succeeded", flush=True)
        else:
            print("Create group failed")


class MyApp(App):
    def build(self):
        global global_list_container
        global current_update_thread

        Window.size = (500, 800)
        screen_manager = ScreenManager()
        screen_manager.add_widget(GroupScreen(name="group_screen"))
        list_screen = ListScreen(name="list_screen")
        global_list_container = list_screen.list_container

        screen_manager.add_widget(list_screen)
        # Get the updated group list from server
        response = stub.GetItems(list_pb2.ItemsRequest(group=group_name, password=group_pass))
        for item in response.items:
            print(item.name, item.checked)
            list_screen.list_container.create_item(item.name, checked=item.checked)  # Call the create_item method with the item name and checked status

        
        current_update_thread = threading.Thread(target=receive_updates, args=(stop_update_event,))
        current_update_thread.start()

        return screen_manager

if __name__ == '__main__':
    if not Config.has_section('myapp'):
        Config.add_section('myapp')
    if not Config.has_option('myapp', 'group_name'):
        Config.set('myapp', 'group_name', 'You are not in a group yet')
    if not Config.has_option('myapp', 'password'):
        Config.set('myapp', 'password', 'You are not in a group yet')   
    
    group_name = Config.get('myapp', 'group_name')
    group_pass = Config.get('myapp', 'password')
    global_list_container = None
    current_update_thread = None
    group_changed = False
    stop_update_event = threading.Event()



    with grpc.insecure_channel('localhost:50058') as channel:
        # Setup stub 
        stub = list_pb2_grpc.ListServiceStub(channel)
        MyApp().run()