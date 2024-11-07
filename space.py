import os
import inspect
import json
import urllib.request
import sys

class Logger:
    def __init__(self, package_name: str):
        self._package_name = package_name
        self._run_id = os.environ.get("TF_VAR_spacelift_run_id", "local")

        self._debug_mode = os.environ.get("SPACELIFT_DEBUG", False) != False

        self._log_color = "\033[36m"
        self._debug_color = "\033[35m"
        self._warn_color = "\033[33m"
        self._error_color = "\033[31m"
        self._end_color = "\033[0m"

    def log(self, message: str):
        print(f"{self._log_color}[{self._run_id}]{self._end_color} ({self._package_name})", message)

    def debug(self, message: str):
        if self._debug_mode:
            print(f"{self._log_color}[{self._run_id}]{self._end_color} ({self._package_name}) "
                  f"{self._debug_color}DEBUG{self._end_color}", message)

    def warn(self, message: str):
        print(f"{self._log_color}[{self._run_id}]{self._end_color} ({self._package_name}) "
              f"{self._warn_color}WARN{self._end_color} ", message)

    def error(self, message: str):
        print(f"{self._error_color}[{self._run_id}] ({self._package_name}) ERROR{self._end_color}", message)

class SpacePy:
    def __init__(self, fn: callable):
        file_name = os.path.basename(inspect.getfile(fn))
        plugin_name = os.path.splitext(file_name)[0]
        self.logger = Logger(plugin_name)

        self.logger.log("Starting SpacePy 1.0.1")

        self._api_token = os.environ.get('SPACELIFT_API_TOKEN', False)
        self._spacelift_domain = os.environ.get('SPACELIFT_DOMAIN', False)
        self._api_enabled = self._api_token != False and self._spacelift_domain != False
        self._workspace_root = os.environ.get('WORKSPACE_ROOT', os.getcwd())

        # This should be the last thing we do in the constructor
        # because we set api_enabled to false if the domain is set up incorrectly.
        if self._spacelift_domain:
            # this must occur after we check if spacelift domain is false
            # because the domain could be set but not start with https://
            if self._spacelift_domain.startswith("https://"):
                if self._spacelift_domain.endswith("/"):
                    self._spacelift_domain = self._spacelift_domain[:-1]
            else:
                self.logger.warn("SPACELIFT_DOMAIN does not start with https://, api calls will fail.")
                self._api_enabled = False

        self._start(fn)

    def _start(self, fn: callable):
        sig = inspect.signature(fn)
        args = {}

        if "query_api" in sig.parameters:

            if not self._api_enabled:
                self.logger.error("API is not enabled, please export \"SPACELIFT_API_TOKEN\" and \"SPACELIFT_DOMAIN\".")
                exit(1)

            args["query_api"] = self.query_api

        if "logger" in sig.parameters:
            args["logger"] = self.logger

        if "plan_json" in sig.parameters:
            args["plan_json"] = self.get_plan_json()

        if "state_before_json" in sig.parameters:
            args["state_before_json"] = self.get_state_before_json()

        fn(**args)

    def get_plan_json(self) -> dict | None:
        plan_json = f"{self._workspace_root}/spacelift.plan.json"
        if not os.path.exists(plan_json):
            self.logger.error("spacelift.plan.json does not exist.")
            return None

        with open(plan_json) as f:
            return json.load(f)

    def get_state_before_json(self) -> dict | None:
        plan_json = f"{self._workspace_root}/spacelift.state.before.json"
        if not os.path.exists(plan_json):
            self.logger.error("spacelift.state.before.json does not exist.")
            return None

        with open(plan_json) as f:
            return json.load(f)

    def query_api(self, query: str, variables: dict=None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_token}"
        }

        data = {
            "query": query,
        }

        if variables is not None:
            data["variables"] = variables

        req = urllib.request.Request(f"{self._spacelift_domain}/graphql", json.dumps(data).encode('utf-8'), headers)
        with urllib.request.urlopen(req) as response:
            resp = json.loads(response.read().decode('utf-8'))

        if "errors" in resp:
            self.logger.error(f"Error: {resp['errors']}")
            return resp
        else:
            return resp

def startup(plugin_path: str, plugin_name: str):
    virtual_env_activator = ""
    if os.path.exists(f"{plugin_path}/requirements.txt"):
        virtual_env_path = f"{plugin_path}/.venv/bin/activate"
        virtual_env_activator = f"source {virtual_env_path} && "

        # check if the virtual environment needs to be initialized
        if not os.path.exists(f"{plugin_path}/.venv"):
            # initialize the virtual environment
            os.system(f"python -m venv {plugin_path}/.venv")
            # Install requirements
            os.system(f"{virtual_env_activator}python -m pip install -r {plugin_path}/requirements.txt")

    # Start the plugin
    os.system(f"{virtual_env_activator}WORKSPACE_ROOT={os.getcwd()} python {plugin_path}/{plugin_name}.py")

def generate(phase: str, plugin_name: str):
    print(f"Generating OpenTofu code for {plugin_name} in the {phase} phase.")

    # check if requirements.txt exists
    requirements = ""
    if os.path.exists("requirements.txt"):
        requirements = f"""
resource "spacelift_mounted_file" "requirements" {{
    context_id    = spacelift_context.this.id
    relative_path = "{plugin_name}/requirements.txt"
    content       = filebase64("${{path.module}}/requirements.txt")
    write_only    = false
}}
        """


    template = f"""
terraform {{
  required_providers {{
    spacelift = {{
      source  = "spacelift-io/spacelift"
      version = ">= 0.0.1"
    }}
  }}
}}

variable "name" {{
  type        = string
  description = "Name of the context"
  default     = "{plugin_name}"
}}

variable "space_id" {{
  type        = string
  description = "ID of the space"
  default     = "root"
}}

variable "spacelift_domain" {{
  type        = string
  description = "fqdn of the spacelift instance (https://spacelift-solutions.app.spacelift.io)"
}}

resource "spacelift_context" "this" {{
  name = var.name

  labels   = ["autoattach:{plugin_name}"]
  space_id = var.space_id

  {phase} = [
    "python /mnt/workspace/{plugin_name}/space.py start {plugin_name}"
  ]
}}

resource "spacelift_mounted_file" "this" {{
  context_id    = spacelift_context.this.id
  relative_path = "{plugin_name}/{plugin_name}.py"
  content       = filebase64("${{path.module}}/{plugin_name}.py")
  write_only    = false
}}

resource "spacelift_mounted_file" "spacepy" {{
  context_id    = spacelift_context.this.id
  relative_path = "{plugin_name}/space.py"
  content       = filebase64("${{path.module}}/space.py")
  write_only    = false
}}
{requirements}

resource "spacelift_environment_variable" "domain" {{
  context_id = spacelift_context.this.id
  name       = "SPACELIFT_DOMAIN"
  value      = var.spacelift_domain
  write_only = false
}}
    """

    with open("main.tf", "w") as f:
        f.write(template)

def main():
    l = Logger("SpacePy")

    # Ensure the startup function was called.
    if len(sys.argv) < 3:
        l.log("SpacePy CLI")
        l.log("Usage: python space.py {command}")
        l.log("")
        l.log("Commands:")
        l.log("  start {plugin_name}")
        l.log("    Start the plugin with the given name.")
        l.log("    \"python space.py start my_custom_app\"")
        l.log(" ")
        l.log("  generate {plugin_name} {phase}")
        l.log("    Generate OpenTofu code to create the plugin.")
        l.log("    Phases: before_apply, after_apply, before_destroy, after_destroy, etc")
        l.log("    \"python space.py generate my_custom_app\"")
        exit(1)

    command = sys.argv[1]
    if command == "start":
        plugin_path = os.path.dirname(os.path.abspath(__file__))
        startup(plugin_path, sys.argv[2])
    elif command == "generate":
        generate(sys.argv[3], sys.argv[2])


if __name__ == "__main__":
    main()