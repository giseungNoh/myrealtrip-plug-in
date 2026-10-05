# ChatGPT / Codex plugin setup

This repository exposes `myrealtrip-curator` as a repo marketplace plugin.

## What changed

- Portable manifest: `src/plugin.json`
- OpenAI/Codex compatibility manifest: `src/.codex-plugin/plugin.json`
- Repo marketplace: `.agents/plugins/marketplace.json`
- Existing skills: `src/skills/*`
- Existing MCP configuration: `src/.mcp.json`

## Install for local testing

Requirements:

- ChatGPT desktop app with plugin support, or Codex CLI with plugin marketplace support.
- GitHub access to this repository.
- Any MCP authentication required by the configured services.

Add this repository as a marketplace:

```bash
codex plugin marketplace add giseungNoh/myrealtrip-plug-in --ref main
```

Then inspect the configured marketplace:

```bash
codex plugin marketplace list
```

Restart the ChatGPT desktop app. Open the Plugins Directory, choose the MyRealTrip Curator marketplace, and install `myrealtrip-curator`.

## During development

To test a branch before merging:

```bash
codex plugin marketplace add giseungNoh/myrealtrip-plug-in --ref chatgpt-plugin-support
```

After repository changes:

```bash
codex plugin marketplace upgrade
```

Restart ChatGPT desktop after refreshing the marketplace.

## ChatGPT web/mobile note

The current plugin bundles MCP server configuration through `src/.mcp.json`. GitHub-imported plugins that declare MCP servers can be marked Desktop only.

For a web/mobile-capable ChatGPT integration, register each MCP connection in ChatGPT Developer mode and obtain its `plugin_asdk_app...` app ID. Then add `src/.app.json` and reference it from `src/.codex-plugin/plugin.json` (or `extensions.com.openai.apps` in the portable manifest).

Do not invent app IDs: they are created by ChatGPT for the account/workspace that registers the MCP connection.

## Marketplace import for managed workspaces

Workspace admins can import the repository from:

`https://github.com/giseungNoh/myrealtrip-plug-in`

The supported manifest is at `.agents/plugins/marketplace.json`.

