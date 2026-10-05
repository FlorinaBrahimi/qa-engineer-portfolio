package com.turnitin.qa;

import java.util.Map;
import java.util.stream.Collectors;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.cloudformation.CloudFormationClient;
import software.amazon.awssdk.services.cloudformation.model.Output;
import software.amazon.awssdk.services.cloudformation.model.Stack;

/**
 * Looks up the deployed stack in CloudFormation so tests never hard-code a URL, table name
 * or function name. Redeploying, or deploying a second stack, needs no test changes:
 *
 * <pre>mvn test -Paws                       # default stack, eu-west-2
 * mvn test -Paws -Daws.stack=my-stack -Daws.region=eu-west-1</pre>
 *
 * Credentials come from the standard AWS chain (environment, ~/.aws, or the CI role).
 */
final class AwsEnvironment {

  static final String STACK = System.getProperty("aws.stack", "submission-service");
  static final Region REGION = Region.of(System.getProperty("aws.region", "eu-west-2"));

  private static Stack stack;
  private static Map<String, String> outputs;
  private static String failure;

  private AwsEnvironment() {}

  private static synchronized void load() {
    if (outputs != null || failure != null) {
      return;
    }
    try (CloudFormationClient cfn = CloudFormationClient.builder().region(REGION).build()) {
      stack = cfn.describeStacks(r -> r.stackName(STACK)).stacks().get(0);
      outputs = stack.outputs().stream().collect(Collectors.toMap(Output::outputKey, Output::outputValue));
    } catch (Exception e) {
      failure = e.getClass().getSimpleName() + ": " + e.getMessage();
    }
  }

  /** True when the stack could be read with the current credentials. */
  static boolean available() {
    load();
    return outputs != null;
  }

  static String failureReason() {
    load();
    return failure;
  }

  static String stackStatus() {
    load();
    return stack.stackStatusAsString();
  }

  static String appUrl() {
    return output("AppUrl");
  }

  static String tableName() {
    return output("TableName");
  }

  static String functionName() {
    return output("FunctionName");
  }

  private static String output(String key) {
    load();
    if (outputs == null) {
      throw new IllegalStateException("Cannot read stack " + STACK + " in " + REGION + ": " + failure);
    }
    return outputs.get(key);
  }
}
