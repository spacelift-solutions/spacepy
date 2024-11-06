# SpacePy

A framework for writing Spacelift plugins using Python.

## Installation

1. Copy `space.py` into your plugins' directory.
2. You're done.

There are no external dependencies, the framework works with Python 3.6 and newer out of the box.

## Usage

To create a plugin, create a new Python file in your plugins' directory and import the framework and add the `@SpacePy` decorator to a function.
```python
from space import SpacePy

@SpacePy
def main(logger, query_api, plan_json, state_before_json):
  pass
```

Generally, you would only add the decorator to a single function, but if you add it to multiple functions, they will all be executed in order.

### Requirements

If you include a `requirements.txt` file in your plugin directory, the framework will create a virtual environment for you and install the dependencies before running your plugin.
Simply run your plugin and these steps will be handled for you.

### Function Signature

All the arguments in your function are optional, but you can use them to interact with Spacelift in different ways.
You can see a full example in this repository in `example_plugin.py`.
Heres how each argument can be used:

#### logger
The logger is a Python logger object that you can use to log messages to the Spacelift console.
```python
from space import SpacePy

@SpacePy
def main(logger):
    logger.info('This is an info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
    logger.debug('This is a debug message') # This is only shown when SPACELIFT_DEBUG=true
```

#### query_api
The query API is a function that you can use to query the Spacelift API.

When you add the `query_api` argument to your function, the framework will ensure the `SPACELIFT_API_TOKEN` and `SPACELIFT_DOMAIN` environment variables are set.
It will authenticate to spacelift using these environment variables for you. The API token is automatically set in the environment for administrative stacks by Spacelift.

```python
from space import SpacePy

@SpacePy
def main(logger, query_api):
    # Run a simple query using the query_api function
    whoamiquery = """
    query {
      viewer {
        id
      }
    }
    """
    whoami = query_api(whoamiquery)
    logger.log(f"Hi, I am {whoami['data']['viewer']['id']}")


    # Run a mutation using the query_api_function
    trigger_run_mutations = """
    mutation Run($stackID: ID!) {
      runResourceCreate(stack: $stackID, proposed: false) {}
    }
    """

    trigger_run_variables = {
        "stackID": "archive-file"
    }

    trigger_run = query_api(trigger_run_mutations, trigger_run_variables)
    logger.log(trigger_run)
```

#### plan_json and state_before_json
The plan JSON is a dictionary that contains the plan that Spacelift has generated for your stack.

Both of these arguments are only available to the framework after a plan or after an apply. If you attempt to use them in a different context, the framework will return `None`.
```python
from space import SpacePy

@SpacePy
def main(logger, plan_json, state_before_json):
    
    # Recommended to check for `None` on both objects before using them.
    if plan_json is None or state_before_json is None:
        logger.error('This function can only be used after a plan or an apply')
        return
    
    # plan_json is available after a plan is ran and will contain the plan data
    logger.log(plan_json)
    
    # state_before_json is available after an apply is ran and will contain the state before the apply.
    logger.log(state_before_json)
```

## Using the framework in Spacelift

### Adding the plugin to Spacelift manually

We highly recommend the portable plugin steps below, but if you wish to add the plugin to Spacelift manually, use the following steps:

1. Add `space.py`, your plugin code and any dependencies to Spacelift in a way the run can access it.
    - You can do this in a few different ways, using a mounted file on a stack directly, using contexts, or by adding it to your git repository directly.
2. Run the plugin by adding a hook with the following command `python3 space.py run {plugin_name}`.
    - `plugin_name` is the name of your plugin file without the `.py` extension.
    - `space.py` and your plugin **must** be in the same directory.
    - If `space.py` is in another directory, pass the full path to it, but do not add that to your `plugin_name`.
        - ex: `python3 /path/to/space.py run my_awesome_plugin` 

### Generating a portable plugin

The framework can also generate terraform for you that will allow you to run your plugin by adding the `{plugin_name}` label to your stacks.

To do this:
1. Generate the TF by running: `python space.py generate {plugin_name} {phase}`
   - `phase` can be any phase in spacelift you wish to run your plugin (e.g. `before_plan`, `after_plan`, `before_apply`, `after_apply`, etc.)
   - `plugin_name` is the name of your plugin file without the `.py` extension
   - The environment variable `SPACELIFT_DOMAIN` is used for api calls, if your function doesnt need that, you can remove it from the generated terraform.
2. Execute the generated terraform in your spacelift account.
3. Add the `{plugin_name}` label to any stack that inherits the space_id you executed the terraform in.
4. Your plugin will now run in the phase you specified.