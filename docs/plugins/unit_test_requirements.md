# NetWORKS Plugin Unit Testing Specification

## Overview

This document specifies the requirements and best practices for unit testing NetWORKS plugins. All plugins should implement comprehensive unit tests to ensure reliability, maintainability, and compatibility with the NetWORKS platform.

## Table of Contents

- [Testing Framework](#testing-framework)
- [Test Organization](#test-organization)
- [Required Test Coverage](#required-test-coverage)
- [Test Structure and Naming](#test-structure-and-naming)
- [Mocking and Fixtures](#mocking-and-fixtures)
- [Running Tests](#running-tests)
- [Integration with CI/CD](#integration-with-cicd)
- [Best Practices](#best-practices)
- [Example Test Suite](#example-test-suite)

---

## Testing Framework

### Required Dependencies

All plugins must use the following testing framework:

- **pytest** (≥7.0.0) - Primary testing framework
- **pytest-qt** (≥4.0.0) - For testing Qt/PySide6 components
- **pytest-cov** (≥4.0.0) - For code coverage reporting
- **pytest-mock** (≥3.10.0) - For enhanced mocking capabilities

### Installation

Add these dependencies to your plugin's `requirements-dev.txt`:

```text
pytest>=7.0.0
pytest-qt>=4.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
```

---

## Test Organization

### Directory Structure

Every plugin must have a `tests/` directory with the following structure:

```
my_plugin/
├── my_plugin.py                 # Plugin implementation
├── lib/                         # Plugin modules (if any)
│   └── helper.py
├── tests/                       # Test directory
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures and configuration
│   ├── test_plugin_core.py      # Tests for main plugin class
│   ├── test_initialization.py   # Tests for initialization/cleanup
│   ├── test_ui_components.py    # Tests for UI elements
│   ├── test_settings.py         # Tests for settings management
│   ├── test_signals.py          # Tests for signal handling
│   └── lib/                     # Tests for lib modules
│       └── test_helper.py
├── manifest.json
├── API.md
├── README.md
└── requirements-dev.txt         # Development dependencies
```

### Test File Naming

- Test files must be named `test_*.py` or `*_test.py`
- Test functions must be named `test_*`
- Test classes must be named `Test*`

---

## Required Test Coverage

### Minimum Coverage Requirements

All plugins must achieve:

- **Overall code coverage**: ≥ 80%
- **Core plugin class**: ≥ 90%
- **Public API methods**: 100%
- **Signal handlers**: ≥ 85%

### Critical Test Categories

Every plugin must include tests for the following:

#### 1. Plugin Lifecycle Tests

**Required Tests:**
- `test_plugin_initialization_success` - Verify successful initialization
- `test_plugin_initialization_with_dependencies` - Test dependency handling
- `test_plugin_initialization_failure` - Test graceful failure handling
- `test_plugin_cleanup_success` - Verify proper cleanup
- `test_plugin_cleanup_with_active_resources` - Test cleanup with open resources
- `test_plugin_state_transitions` - Verify state changes (if applicable)

**Example:**
```python
def test_plugin_initialization_success(mock_app, plugin_info):
    """Test successful plugin initialization."""
    plugin = MyPlugin()
    result = plugin.initialize(mock_app, plugin_info)
    
    assert result is True
    assert plugin._initialized is True
    assert plugin.app is mock_app
    assert plugin.device_manager is mock_app.device_manager
```

#### 2. Signal Handling Tests

**Required Tests:**
- `test_signal_connections` - Verify signals are properly connected
- `test_signal_disconnections` - Verify signals are properly disconnected
- `test_device_added_signal` - Test response to device_added
- `test_device_removed_signal` - Test response to device_removed
- `test_device_changed_signal` - Test response to device_changed
- `test_custom_signals` - Test any plugin-specific signals

**Example:**
```python
def test_device_added_signal(plugin, mock_device_manager, sample_device):
    """Test plugin responds correctly to device_added signal."""
    # Emit signal
    mock_device_manager.device_added.emit(sample_device)
    
    # Verify plugin responded appropriately
    assert sample_device.get_id() in plugin.devices
```

#### 3. UI Component Tests

**Required Tests (if plugin has UI):**
- `test_ui_creation` - Verify UI components are created correctly
- `test_toolbar_actions` - Test toolbar action creation and behavior
- `test_menu_actions` - Test menu action creation and behavior
- `test_device_panels` - Test device panel creation and updates
- `test_dock_widgets` - Test dock widget registration
- `test_ui_updates` - Test UI updates in response to data changes
- `test_ui_cleanup` - Verify UI components are properly removed

**Example:**
```python
def test_device_panels(plugin):
    """Test device panel creation."""
    panels = plugin.get_device_panels()
    
    assert isinstance(panels, list)
    assert len(panels) > 0
    
    for name, widget in panels:
        assert isinstance(name, str)
        assert widget is not None
```

#### 4. Settings Management Tests

**Required Tests (if plugin has settings):**
- `test_get_settings` - Verify settings structure
- `test_update_setting_valid` - Test valid setting updates
- `test_update_setting_invalid` - Test invalid setting rejection
- `test_settings_persistence` - Test settings save/load
- `test_settings_validation` - Test setting value validation
- `test_setting_types` - Test all setting types (string, int, float, bool, choice)

**Example:**
```python
def test_update_setting_valid(plugin):
    """Test updating a setting with a valid value."""
    result = plugin.update_setting("log_level", "DEBUG")
    
    assert result is True
    assert plugin.settings["log_level"]["value"] == "DEBUG"

def test_update_setting_invalid(plugin):
    """Test updating a setting with an invalid value."""
    result = plugin.update_setting("nonexistent_setting", "value")
    
    assert result is False
```

#### 5. Device Property Tests

**Required Tests (if plugin adds device properties):**
- `test_device_property_naming` - Verify property naming convention
- `test_device_property_setting` - Test setting properties
- `test_device_property_getting` - Test retrieving properties
- `test_device_property_types` - Test property type handling
- `test_property_documentation` - Verify properties are documented in API.md

**Example:**
```python
def test_device_property_naming(plugin, sample_device):
    """Test plugin uses correct property naming convention."""
    plugin.set_custom_property(sample_device, "test_value")
    
    # Verify property follows naming convention
    property_name = f"{plugin.plugin_info.id}:custom_property"
    assert sample_device.has_property(property_name)
```

#### 6. Error Handling Tests

**Required Tests:**
- `test_exception_handling` - Verify exceptions are caught and logged
- `test_missing_dependencies` - Test behavior with missing dependencies
- `test_invalid_input_handling` - Test handling of invalid inputs
- `test_resource_unavailable` - Test behavior when resources are unavailable
- `test_concurrent_access` - Test thread-safe operations (if applicable)

**Example:**
```python
def test_exception_handling(plugin, caplog):
    """Test plugin handles exceptions gracefully."""
    # Trigger an error condition
    plugin.process_invalid_data(None)
    
    # Verify exception was logged
    assert "Error in my plugin" in caplog.text
    # Verify plugin remains in valid state
    assert plugin._initialized is True
```

#### 7. Plugin Interaction Tests

**Required Tests (if plugin interacts with others):**
- `test_get_other_plugin` - Test retrieving other plugin instances
- `test_missing_dependency_plugin` - Test behavior when dependency is unavailable
- `test_cross_plugin_communication` - Test API calls to other plugins
- `test_dependency_version_check` - Test version compatibility checking

#### 8. Data Persistence Tests

**Required Tests (if plugin stores data):**
- `test_data_save` - Test saving data to disk
- `test_data_load` - Test loading data from disk
- `test_data_migration` - Test handling old data formats
- `test_corrupted_data_handling` - Test handling of corrupted data files
- `test_workspace_isolation` - Test workspace-specific data isolation

---

## Test Structure and Naming

### Test Function Structure

All tests should follow the **Arrange-Act-Assert** pattern:

```python
def test_feature_name(fixtures):
    """Clear description of what is being tested."""
    # Arrange - Set up test conditions
    plugin = MyPlugin()
    mock_app = create_mock_app()
    
    # Act - Execute the behavior being tested
    result = plugin.initialize(mock_app, plugin_info)
    
    # Assert - Verify the expected outcome
    assert result is True
    assert plugin._initialized is True
```

### Naming Conventions

Use descriptive test names that clearly indicate:
1. What is being tested
2. Under what conditions
3. What the expected result is

**Good Examples:**
- `test_initialization_succeeds_with_valid_config`
- `test_cleanup_disconnects_all_signals`
- `test_setting_update_rejects_invalid_type`

**Poor Examples:**
- `test_init`
- `test_1`
- `test_feature`

### Docstrings

Every test must have a docstring explaining:
- What is being tested
- Why it's important
- Any special considerations

```python
def test_plugin_handles_missing_device_manager(plugin, mock_app_no_device_manager):
    """
    Test plugin gracefully handles missing device_manager.
    
    This ensures the plugin can initialize even if the device_manager
    is not available, which may occur during certain startup sequences
    or in testing environments.
    """
    # Test implementation
```

---

## Mocking and Fixtures

### Required Fixtures (conftest.py)

Every plugin test suite must define these core fixtures in `conftest.py`:

```python
import pytest
from unittest.mock import Mock, MagicMock
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Provide QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def mock_app():
    """Provide mock application instance."""
    app = Mock()
    app.device_manager = Mock()
    app.main_window = Mock()
    app.config = Mock()
    app.plugin_manager = Mock()
    return app

@pytest.fixture
def plugin_info():
    """Provide plugin info object."""
    info = Mock()
    info.id = "test_plugin"
    info.name = "Test Plugin"
    info.version = "1.0.0"
    info.path = "/path/to/plugin"
    info.loaded = True
    return info

@pytest.fixture
def sample_device():
    """Provide a sample device for testing."""
    from src.core.device import Device
    device = Device()
    device.set_property("id", "test-device-1")
    device.set_property("alias", "Test Device")
    device.set_property("ip", "192.168.1.100")
    return device

@pytest.fixture
def initialized_plugin(mock_app, plugin_info):
    """Provide an initialized plugin instance."""
    from my_plugin import MyPlugin
    plugin = MyPlugin()
    plugin.initialize(mock_app, plugin_info)
    yield plugin
    plugin.cleanup()
```

### Mocking Guidelines

1. **Mock External Dependencies**: Always mock external systems (network, files, APIs)
2. **Mock Qt Components**: Use pytest-qt's qtbot fixture for Qt widget testing
3. **Mock Signals**: Use MagicMock for PySide6 Signal objects
4. **Mock Time**: Use time-freezing for time-dependent tests
5. **Mock File I/O**: Use pytest's tmp_path fixture for file operations

**Example:**
```python
def test_network_scan(plugin, mocker, tmp_path):
    """Test network scanning with mocked network calls."""
    # Mock the network scan function
    mock_scan = mocker.patch('nmap.PortScanner')
    mock_scan.return_value.scan.return_value = {'hosts': []}
    
    # Mock file output
    output_file = tmp_path / "scan_results.json"
    
    # Execute test
    plugin.scan_network("192.168.1.0/24", output_file)
    
    # Verify
    mock_scan.return_value.scan.assert_called_once()
```

---

## Running Tests

### Command Line Execution

Plugins must support the following test commands:

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=my_plugin --cov-report=html --cov-report=term
```

**Run specific test file:**
```bash
pytest tests/test_initialization.py
```

**Run with verbose output:**
```bash
pytest -v
```

**Run and show print statements:**
```bash
pytest -s
```

### pytest.ini Configuration

Create a `pytest.ini` file in the plugin root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = 
    -ra
    --strict-markers
    --cov=my_plugin
    --cov-branch
    --cov-report=term-missing:skip-covered
    --cov-report=html
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    ui: marks tests that require UI components
```

### Coverage Configuration

Create a `.coveragerc` file:

```ini
[run]
source = .
omit = 
    tests/*
    */site-packages/*
    */__pycache__/*
    */venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

---

## Integration with CI/CD

### GitHub Actions Example

Create `.github/workflows/tests.yml`:

```yaml
name: Plugin Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, '3.10', '3.11']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests with pytest
      run: |
        pytest --cov=my_plugin --cov-report=xml --cov-report=term
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

---

## Best Practices

### 1. Test Independence

Each test must be completely independent:

```python
# GOOD - Each test creates its own plugin instance
def test_feature_a(mock_app, plugin_info):
    plugin = MyPlugin()
    plugin.initialize(mock_app, plugin_info)
    # test code
    plugin.cleanup()

def test_feature_b(mock_app, plugin_info):
    plugin = MyPlugin()
    plugin.initialize(mock_app, plugin_info)
    # test code
    plugin.cleanup()

# BAD - Tests share state
plugin = None

def test_feature_a(mock_app, plugin_info):
    global plugin
    plugin = MyPlugin()
    plugin.initialize(mock_app, plugin_info)
    # test code

def test_feature_b():
    # Uses plugin from previous test - BAD!
    # test code
```

### 2. Use Parametrized Tests

For testing multiple scenarios:

```python
@pytest.mark.parametrize("setting_id,value,expected", [
    ("log_level", "DEBUG", True),
    ("log_level", "INFO", True),
    ("log_level", "INVALID", False),
    ("timeout", 30, True),
    ("timeout", -1, False),
])
def test_setting_validation(plugin, setting_id, value, expected):
    """Test setting validation with various inputs."""
    result = plugin.update_setting(setting_id, value)
    assert result == expected
```

### 3. Test Edge Cases

Always test boundary conditions:

```python
def test_empty_device_list(plugin):
    """Test behavior with no devices."""
    result = plugin.process_devices([])
    assert result == []

def test_single_device(plugin, sample_device):
    """Test behavior with one device."""
    result = plugin.process_devices([sample_device])
    assert len(result) == 1

def test_many_devices(plugin):
    """Test behavior with many devices."""
    devices = [create_device(i) for i in range(1000)]
    result = plugin.process_devices(devices)
    assert len(result) == 1000
```

### 4. Use Fixtures for Setup/Teardown

Avoid repetitive setup code:

```python
@pytest.fixture
def plugin_with_test_data(initialized_plugin, sample_devices):
    """Provide plugin with pre-loaded test data."""
    for device in sample_devices:
        initialized_plugin.add_device(device)
    return initialized_plugin

def test_feature_with_data(plugin_with_test_data):
    """Test uses pre-configured plugin."""
    # Test implementation
```

### 5. Test Async Operations

For plugins with background tasks:

```python
@pytest.mark.asyncio
async def test_async_operation(plugin):
    """Test asynchronous operation completes correctly."""
    result = await plugin.async_operation()
    assert result is not None

def test_threaded_operation(plugin, qtbot):
    """Test threaded operation with signals."""
    with qtbot.waitSignal(plugin.operation_completed, timeout=5000):
        plugin.start_background_task()
```

### 6. Document Test Failures

Include helpful failure messages:

```python
def test_device_property(plugin, sample_device):
    """Test device property is set correctly."""
    plugin.set_device_property(sample_device, "test_prop", "value")
    
    actual = sample_device.get_property("test_prop")
    assert actual == "value", \
        f"Expected property 'test_prop' to be 'value', got '{actual}'"
```

---

## Example Test Suite

Here's a complete example test suite for a simple plugin:

**tests/conftest.py:**
```python
import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    """Provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def mock_app():
    """Provide mock application."""
    app = Mock()
    app.device_manager = Mock()
    app.device_manager.device_added = Mock()
    app.device_manager.device_removed = Mock()
    app.main_window = Mock()
    app.config = Mock()
    app.plugin_manager = Mock()
    return app

@pytest.fixture
def plugin_info():
    """Provide plugin info."""
    info = Mock()
    info.id = "example_plugin"
    info.name = "Example Plugin"
    info.version = "1.0.0"
    info.path = "/path/to/plugin"
    return info

@pytest.fixture
def plugin():
    """Provide fresh plugin instance."""
    from example_plugin import ExamplePlugin
    return ExamplePlugin()

@pytest.fixture
def initialized_plugin(plugin, mock_app, plugin_info):
    """Provide initialized plugin."""
    plugin.initialize(mock_app, plugin_info)
    yield plugin
    plugin.cleanup()
```

**tests/test_plugin_core.py:**
```python
import pytest
from example_plugin import ExamplePlugin

class TestPluginCore:
    """Test core plugin functionality."""
    
    def test_plugin_creation(self):
        """Test plugin can be instantiated."""
        plugin = ExamplePlugin()
        assert plugin is not None
        assert plugin.name == "Example Plugin"
    
    def test_initialization_success(self, plugin, mock_app, plugin_info):
        """Test successful plugin initialization."""
        result = plugin.initialize(mock_app, plugin_info)
        
        assert result is True
        assert plugin._initialized is True
        assert plugin.app is mock_app
        assert plugin.device_manager is mock_app.device_manager
    
    def test_initialization_stores_references(self, initialized_plugin, mock_app):
        """Test initialization stores all required references."""
        assert initialized_plugin.app is mock_app
        assert initialized_plugin.device_manager is mock_app.device_manager
        assert initialized_plugin.main_window is mock_app.main_window
        assert initialized_plugin.config is mock_app.config
    
    def test_cleanup_success(self, initialized_plugin):
        """Test plugin cleanup completes successfully."""
        result = initialized_plugin.cleanup()
        assert result is True
    
    def test_cleanup_disconnects_signals(self, initialized_plugin, mock_app):
        """Test cleanup disconnects all signals."""
        initialized_plugin.cleanup()
        
        # Verify signal disconnections
        mock_app.device_manager.device_added.disconnect.assert_called()


class TestSignalHandling:
    """Test signal handling."""
    
    def test_connects_to_device_signals(self, initialized_plugin, mock_app):
        """Test plugin connects to required device signals."""
        # Verify connections were made
        mock_app.device_manager.device_added.connect.assert_called()
        mock_app.device_manager.device_removed.connect.assert_called()
    
    def test_device_added_handler(self, initialized_plugin, mock_app):
        """Test device_added signal handler."""
        device = Mock()
        device.get_id.return_value = "test-123"
        
        # Trigger signal
        initialized_plugin.on_device_added(device)
        
        # Verify plugin responded
        assert "test-123" in initialized_plugin.tracked_devices


class TestSettings:
    """Test settings management."""
    
    def test_get_settings_structure(self, initialized_plugin):
        """Test get_settings returns correct structure."""
        settings = initialized_plugin.get_settings()
        
        assert isinstance(settings, dict)
        assert "log_level" in settings
        assert "name" in settings["log_level"]
        assert "type" in settings["log_level"]
        assert "value" in settings["log_level"]
    
    @pytest.mark.parametrize("setting,value,expected", [
        ("log_level", "DEBUG", True),
        ("log_level", "INFO", True),
        ("log_level", "INVALID", False),
        ("invalid_setting", "value", False),
    ])
    def test_update_setting(self, initialized_plugin, setting, value, expected):
        """Test setting updates with various inputs."""
        result = initialized_plugin.update_setting(setting, value)
        assert result == expected
```

**tests/test_ui_components.py:**
```python
import pytest
from PySide6.QtWidgets import QWidget, QLabel

class TestUIComponents:
    """Test UI component creation."""
    
    def test_creates_device_panels(self, initialized_plugin, qapp):
        """Test plugin creates device panels."""
        panels = initialized_plugin.get_device_panels()
        
        assert isinstance(panels, list)
        assert len(panels) > 0
        
        name, widget = panels[0]
        assert isinstance(name, str)
        assert isinstance(widget, QWidget)
    
    def test_panel_has_correct_title(self, initialized_plugin, qapp):
        """Test device panel has correct title."""
        panels = initialized_plugin.get_device_panels()
        name, widget = panels[0]
        
        assert name == "Example Panel"
    
    def test_creates_toolbar_actions(self, initialized_plugin, qapp):
        """Test plugin creates toolbar actions."""
        actions = initialized_plugin.get_toolbar_actions()
        
        assert isinstance(actions, list)
        if len(actions) > 0:
            assert hasattr(actions[0], 'triggered')
```

---

## Checklist for Plugin Developers

Before submitting a plugin, verify:

- [ ] All required test categories have tests
- [ ] Test coverage is ≥ 80% overall
- [ ] Core plugin class has ≥ 90% coverage
- [ ] All public API methods have tests
- [ ] Tests run successfully with `pytest`
- [ ] Tests run successfully with coverage reporting
- [ ] No warnings during test execution
- [ ] All tests have descriptive names and docstrings
- [ ] `conftest.py` contains required fixtures
- [ ] `pytest.ini` is configured correctly
- [ ] Mock objects are used for external dependencies
- [ ] Tests are independent and can run in any order
- [ ] Edge cases and error conditions are tested
- [ ] Signal connections/disconnections are tested
- [ ] UI components are tested (if applicable)
- [ ] Settings management is tested (if applicable)
- [ ] Documentation includes test running instructions

---

## Continuous Improvement

### Test Maintenance

- Review and update tests when plugin functionality changes
- Add tests for new features before implementation (TDD)
- Remove or update tests for deprecated features
- Keep test fixtures up to date with API changes

### Code Review

During code review, verify:
- New features have corresponding tests
- Test coverage hasn't decreased
- Tests follow the specification
- Mock objects are used appropriately
- Tests are clear and maintainable

---

## Conclusion

Following this specification ensures that NetWORKS plugins are:
- **Reliable**: Comprehensive tests catch bugs early
- **Maintainable**: Clear tests document expected behavior
- **Compatible**: Tests verify integration with the platform
- **Professional**: Consistent testing approach across all plugins

Plugins that don't meet these testing requirements should not be merged into the main repository.