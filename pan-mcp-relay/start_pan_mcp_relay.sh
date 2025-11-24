#!/bin/bash
rm -f mcp_relay.log
uvx pan-mcp-relay --config-file ./mcp-relay.yaml --transport=http -H 0.0.0.0 -p 8800 -d 2>&1 | tee mcp_relay.log