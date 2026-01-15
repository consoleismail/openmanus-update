#!/usr/bin/env python3
"""
Test script for OpenManus application
Tests basic functionality without requiring API calls
"""
import sys
import os

# Add the project to path
sys.path.insert(0, "/home/admin123/Desktop/OpenManus")

def test_imports():
    """Test that all main components can be imported"""
    print("=" * 60)
    print("Testing OpenManus Application")
    print("=" * 60)
    
    tests = [
        ("app.agent.manus", "Manus agent"),
        ("app.agent.sandbox_agent", "Sandbox agent"),
        ("app.tool", "Tool collection"),
        ("app.config", "Configuration"),
        ("app.logger", "Logger"),
    ]
    
    results = []
    for module_name, description in tests:
        try:
            __import__(module_name)
            print(f"✓ {description}: OK")
            results.append(True)
        except Exception as e:
            print(f"✗ {description}: FAILED - {e}")
            results.append(False)
    
    return all(results)

def test_config():
    """Test configuration loading"""
    print("\n" + "=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    
    try:
        from app.config import config
        print(f"✓ Config loaded successfully")
        print(f"  - Workspace root: {config.workspace_root}")
        print(f"  - LLM model: {config.llm.model if hasattr(config.llm, 'model') else 'N/A'}")
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False

def test_agent_structure():
    """Test agent class structure"""
    print("\n" + "=" * 60)
    print("Testing Agent Structure")
    print("=" * 60)
    
    try:
        from app.agent.manus import Manus
        from app.tool import ToolCollection
        
        # Check if Manus has required attributes
        print(f"✓ Manus class loaded")
        print(f"  - Name: {Manus.__name__}")
        print(f"  - Description: {Manus.__doc__}")
        
        # Check available tools
        from app.tool.python_execute import PythonExecute
        from app.tool.str_replace_editor import StrReplaceEditor
        from app.tool.browser_use_tool import BrowserUseTool
        
        print(f"✓ Core tools available:")
        print(f"  - PythonExecute")
        print(f"  - StrReplaceEditor")
        print(f"  - BrowserUseTool")
        
        return True
    except Exception as e:
        print(f"✗ Agent structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workspace():
    """Test workspace directory"""
    print("\n" + "=" * 60)
    print("Testing Workspace")
    print("=" * 60)
    
    try:
        from app.config import config
        workspace = config.workspace_root
        
        if os.path.exists(workspace):
            print(f"✓ Workspace exists: {workspace}")
            return True
        else:
            print(f"✗ Workspace does not exist: {workspace}")
            return False
    except Exception as e:
        print(f"✗ Workspace test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\nOpenManus Application Test Suite")
    print("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Agent Structure Test", test_agent_structure),
        ("Workspace Test", test_workspace),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n✓ All tests passed! The application is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
