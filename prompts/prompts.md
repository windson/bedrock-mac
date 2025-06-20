Create a AWS CDK Project to create two Action group Lambda functions in Python programming language for Amazon Bedrock's Agent that does the following.

1st Lambda:
- Approve Leaves
- Reject Leaves

2nd Lambda:
- Apply Leave
- Cancel Leave

Things to keep aware of:

- Refer to the examplereference.md for sample python lambda handlers.
- Ensure the functions that perform apply, cancel, reject and approve leave tasks you implement in these two lambda handlers can accept as minimal input arguments as possible. Limit parameters if required, to max 3 when performing leave actions as appropriate.
- Use primitive data types and use int for ID if applicable.
- Use dynamodb to store the data.
- Also generate sample utility scripts to ingest synthetic data.
- use lms_cdk directory to create the AWS CDK project.

---

With two agent lambda functions, Add a third agent lamda funtion that notifies both approver and applier of leave.

Modify the changes in dynamodb table

For all the users use pavankrn@amazon.com as email id and read it from environment file. For all approvers use pavanraonavule@gmail.com as email id from .env file

- Use SNS to notify via email. The email should have leave info.
- Update seed and query utility scripts accordingly.
- Update readme files and other files as appropriate.
- Update bedrock_agent_schemas.json in case of any changes
Directory References:  @Documentation  @KB  @lms_cdk

---

Can you get my leave balance ? My emp id is 1005
can you apply leave for my marriage? from 17th June 2025 to 21st June 2025?
can you get the leave status?
