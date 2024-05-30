from chalice import Chalice
from chalice.app import SQSEvent, SQSRecord
import botocore
import boto3
from typing import Callable, Optional
import uuid
import os

def TaskingControllerFactory(queue_name: str, message_group_id: str) -> 'TaskingController':
    """
    The TaskingControllerFactory allows messages to be sent to a SQS queue, enabling
    asynchronous processing of messages. Its recommended to use a FIFO queue rather than a standard
    queue as AWS guarentees exactly once processing with no duplicates.
    Some useful usecases of this are sending logs, analytics, exception reporting, 
    and anything else that should be handled in a way that does not hold up the 
    function processing a users request.

    :param queue_name: Preconfigured SQS queue to use for messaging
    :param message_group_id: The tag that specifies that a message belongs to a specific message group
    :returns TaskingController: A new TaskingController instance
    """
    class TaskingController:
        def __init__(self):
            sqs = boto3.resource('sqs', region_name='us-east-2')
            self.__queue = sqs.get_queue_by_name(QueueName=queue_name)
            q = queue_name.replace('.', '_').replace('-', '_')
            self.handler_name = f'on_message_{q}'
            self.__message_handler = None
            self.__current_app = None

        def register_handler(self, app: Chalice) -> None:
            """
            Registers the TaskingControllers SQS handler, MUST be called within app.py main entrypoint.

            :param app: Main chalice app
            :return: None
            """
            self.__current_app = app
            def make_handler():
                def func1(event: SQSEvent) -> None:
                    for record in event:
                        try:
                            print('Dequeue message', record.body)
                            if self.__message_handler and callable(self.__message_handler):
                                self.__message_handler(record)
                        except Exception as e:
                            raise e
                func1.__name__ = self.handler_name
                return func1
            register_fn = self.__current_app.on_sqs_message(queue=queue_name, name=self.handler_name, batch_size=1)
            handler = make_handler()
            register_fn(handler)
            setattr(self.__current_app, self.handler_name, handler)

        def set_message_handler(self, message_handler: Callable[[SQSRecord], None]) -> None:
            """
            Sets the message handler for incoming SQSREcord's.

            :param message_handler: Handler for incoming SQS messages
            :return: None
            """
            self.__message_handler = message_handler

        def post(self, message_body: str, message_attributes: dict=None) -> dict:
            """
            Send a message to the configured Tasking Queue

            :param message_body: The body text of the message.
            :param message_attributes: Custom attributes of the message. These are key-value
                                    pairs that can be whatever you want.
            :return: The response from SQS that contains the assigned message ID.
            """
            print('Enqueueing message', message_body)
            stage = os.environ.get('STAGE')
            if stage == 'dev':
                from chalice.test import Client
                if self.__current_app is None:
                    raise RuntimeError(
                        "Can only mock SQS queue behaviour if it's registered to an app."
                    )
                with Client(self.__current_app, stage_name=stage) as client:
                    client.lambda_.invoke(self.handler_name,
                                          client.events.generate_sqs_event([message_body], queue_name))
                return None

            if not message_attributes:
                message_attributes = {}

            try:
                response = self.__queue.send_message(
                    MessageBody=message_body,
                    MessageAttributes=message_attributes,
                    MessageGroupId=message_group_id,
                    MessageDeduplicationId=str(uuid.uuid4())
                )
            except botocore.exceptions.ClientError as error:
                raise error
            else:
                print(response)
                return response

    return TaskingController()