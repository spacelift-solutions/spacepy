from space import SpacePy

@SpacePy
def main(logger, query_api, plan_json, state_before_json):

    # Standard Logging
    logger.log("Hello, world!")

    # Debug Logging, only appears when SPACELIFT_DEBUG=true
    logger.debug("This is a debug message.")

    # Warn and Error Logging
    logger.warn("This is a warning message.")
    logger.error("This is an error message.")

    # plan_json is available after a plan is ran and will contain the plan data
    logger.log(plan_json)

    # state_before_json is available after an apply is ran and will contain the state before the apply.
    logger.log(state_before_json)


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