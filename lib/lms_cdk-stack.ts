import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as path from 'path';
import * as fs from 'fs';

// Load environment variables from .env file
const envPath = path.join(__dirname, '../.env');
let EMPLOYEE_EMAIL = 'employee@example.com';
let APPROVER_EMAIL = 'approver@example.com';

// Read from .env file if it exists
if (fs.existsSync(envPath)) {
  const envConfig = fs.readFileSync(envPath, 'utf8')
    .split('\n')
    .filter(line => line.trim() !== '' && !line.startsWith('#'))
    .reduce((acc: Record<string, string>, line) => {
      const [key, value] = line.split('=');
      if (key && value) {
        acc[key.trim()] = value.trim();
      }
      return acc;
    }, {});
  
  if (envConfig.EMPLOYEE_EMAIL) {
    EMPLOYEE_EMAIL = envConfig.EMPLOYEE_EMAIL;
  }
  if (envConfig.APPROVER_EMAIL) {
    APPROVER_EMAIL = envConfig.APPROVER_EMAIL;
  }
}

export class LmsCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create DynamoDB table for leave management
    const leaveTable = new dynamodb.Table(this, 'LeaveManagementTable', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.NUMBER },
      sortKey: { name: 'type', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development only
    });

    // Create SNS topic for leave notifications
    const leaveNotificationTopic = new sns.Topic(this, 'LeaveNotificationTopic', {
      displayName: 'Leave Management Notifications',
    });

    // Create Lambda for leave approval/rejection
    const leaveApprovalLambda = new lambda.Function(this, 'LeaveApprovalLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'leave_approval.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/leave_approval')),
      environment: {
        TABLE_NAME: leaveTable.tableName,
      },
    });

    // Create Lambda for leave application/cancellation
    const leaveApplicationLambda = new lambda.Function(this, 'LeaveApplicationLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'leave_application.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/leave_application')),
      environment: {
        TABLE_NAME: leaveTable.tableName,
      },
    });

    // Create Lambda for leave notifications
    const leaveNotificationLambda = new lambda.Function(this, 'LeaveNotificationLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'leave_notification.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/leave_notification')),
      timeout: cdk.Duration.seconds(15),
      environment: {
        TABLE_NAME: leaveTable.tableName,
        SNS_TOPIC_ARN: leaveNotificationTopic.topicArn,
        EMPLOYEE_EMAIL: EMPLOYEE_EMAIL,
        APPROVER_EMAIL: APPROVER_EMAIL,
      },
    });

    // Grant permissions to Lambda functions
    leaveTable.grantReadWriteData(leaveApprovalLambda);
    leaveTable.grantReadWriteData(leaveApplicationLambda);
    leaveTable.grantReadWriteData(leaveNotificationLambda);
    
    // Grant SNS publish permissions to notification Lambda
    leaveNotificationTopic.grantPublish(leaveNotificationLambda);
    
    // Subscribe the approver and employee emails to the SNS topic
    new sns.Subscription(this, 'ApproverEmailSubscription', {
      topic: leaveNotificationTopic,
      protocol: sns.SubscriptionProtocol.EMAIL,
      endpoint: APPROVER_EMAIL,
      filterPolicy: {
        email: sns.SubscriptionFilter.stringFilter({
          allowlist: [APPROVER_EMAIL]
        })
      }
    });
    
    new sns.Subscription(this, 'EmployeeEmailSubscription', {
      topic: leaveNotificationTopic,
      protocol: sns.SubscriptionProtocol.EMAIL,
      endpoint: EMPLOYEE_EMAIL,
      filterPolicy: {
        email: sns.SubscriptionFilter.stringFilter({
          allowlist: [EMPLOYEE_EMAIL]
        })
      }
    });

    // Create IAM policy for Bedrock to invoke Lambda
    const bedrockPrincipal = new iam.ServicePrincipal('bedrock.amazonaws.com');
    
    // Add resource-based policy to allow Bedrock to invoke the Lambda functions
    leaveApprovalLambda.addPermission('BedrockInvokePermission', {
      principal: bedrockPrincipal,
      action: 'lambda:InvokeFunction',
    });

    leaveApplicationLambda.addPermission('BedrockInvokePermission', {
      principal: bedrockPrincipal,
      action: 'lambda:InvokeFunction',
    });

    leaveNotificationLambda.addPermission('BedrockInvokePermission', {
      principal: bedrockPrincipal,
      action: 'lambda:InvokeFunction',
    });

    // Output the Lambda ARNs and DynamoDB table name
    new cdk.CfnOutput(this, 'LeaveApprovalLambdaArn', {
      value: leaveApprovalLambda.functionArn,
      description: 'ARN of the Leave Approval Lambda function',
    });

    new cdk.CfnOutput(this, 'LeaveApplicationLambdaArn', {
      value: leaveApplicationLambda.functionArn,
      description: 'ARN of the Leave Application Lambda function',
    });

    new cdk.CfnOutput(this, 'LeaveNotificationLambdaArn', {
      value: leaveNotificationLambda.functionArn,
      description: 'ARN of the Leave Notification Lambda function',
    });

    new cdk.CfnOutput(this, 'LeaveTableName', {
      value: leaveTable.tableName,
      description: 'Name of the DynamoDB table for leave management',
    });

    new cdk.CfnOutput(this, 'LeaveNotificationTopicArn', {
      value: leaveNotificationTopic.topicArn,
      description: 'ARN of the SNS topic for leave notifications',
    });
  }
}