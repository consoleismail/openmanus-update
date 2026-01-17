# WorkCo: From Reactive Assistant to Proactive Companion

This document outlines the architectural and behavioral changes required to transform OpenManus into **WorkCo**, a proactive AI companion.

## 1. Persona Transformation

| Feature | OpenManus (Current) | WorkCo (Target) |
| :--- | :--- | :--- |
| **Role** | All-capable AI assistant | Proactive AI companion |
| **Interaction** | Reactive: Waits for prompts | Proactive: Anticipates needs |
| **Goal** | Solve the presented task | Solve tasks and suggest next steps |
| **Tone** | Professional & Efficient | Collaborative & Forward-thinking |

## 2. Architectural Changes

### 2.1. Agent Renaming
- Rename `Manus` class to `WorkCo` in `app/agent/manus.py`.
- Update agent metadata (name, description).

### 2.2. Prompt Engineering
- **System Prompt**: Redefine the identity as a companion that looks ahead.
- **Next Step Prompt**: Add instructions to identify dependencies and future requirements during the execution process.

### 2.3. Enhanced Termination Tool
- Modify the `terminate` tool to include a `proactive_suggestions` field.
- The agent must provide at least 2-3 suggestions for what the user might want to do next based on the completed task.

## 3. Implementation Plan

1. **Update `app/prompt/manus.py`**: Rewrite the system and next-step prompts.
2. **Update `app/tool/terminate.py`**: Add the `proactive_suggestions` parameter.
3. **Update `app/agent/manus.py`**: Rename the class and update its configuration.
4. **Update `app/agent/toolcall.py`**: Ensure the agent logic captures and displays proactive suggestions during termination.
