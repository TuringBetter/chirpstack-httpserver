import os
import sys

import grpc
from chirpstack_api import api

# Configuration.

# This must point to the API interface.
server = "49.232.192.237:18080"

# The DevEUI for which you want to enqueue the downlink.
dev_eui = "aabbccdd00000003"

# The API token (retrieved using the web-interface).
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjQyOTVmNTUxLTU5YzEtNGIwOS1iMmRhLTBkNjFmYTQ2YmI1NiIsInR5cCI6ImtleSJ9.cgiNxrWfEuPjgwHOQs6t_wrXzH0q7vC_NoN42Y68r4Q"

if __name__ == "__main__":
  # Connect without using TLS.
  channel = grpc.insecure_channel(server)

  # Device-queue API client.
  client = api.DeviceServiceStub(channel)

  # Define the API key meta-data.
  auth_token = [("authorization", "Bearer %s" % api_token)]

  # Construct request.
  req = api.EnqueueDeviceQueueItemRequest()
  req.queue_item.confirmed = False
  req.queue_item.data = bytes([0x05, 0x05, 0x05])
  req.queue_item.dev_eui = dev_eui
  req.queue_item.f_port = 10

  resp = client.Enqueue(req, metadata=auth_token)

  # Print the downlink id
  print(resp.id)
