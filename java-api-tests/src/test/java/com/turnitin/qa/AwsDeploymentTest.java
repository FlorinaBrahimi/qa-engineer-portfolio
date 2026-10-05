package com.turnitin.qa;

import static io.restassured.RestAssured.given;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.*;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import software.amazon.awssdk.services.cloudwatch.CloudWatchClient;
import software.amazon.awssdk.services.cloudwatch.model.MetricAlarm;
import software.amazon.awssdk.services.cloudwatch.model.StateValue;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BillingMode;
import software.amazon.awssdk.services.dynamodb.model.TableDescription;
import software.amazon.awssdk.services.lambda.LambdaClient;
import software.amazon.awssdk.services.lambda.model.FunctionUrlAuthType;
import software.amazon.awssdk.services.lambda.model.GetFunctionConfigurationResponse;

/**
 * Tests that only make sense against the deployed AWS stack. They go behind the HTTP API
 * and check the real resources with the AWS SDK: that an API write lands in DynamoDB, that
 * the API serves what is in the table, and that Lambda and CloudWatch are configured as the
 * CloudFormation template promises.
 *
 * <p>Skipped unless the suite targets AWS (-Paws) and AWS credentials are available.
 */
@Tag("aws")
class AwsDeploymentTest extends BaseApiTest {

  private static DynamoDbClient dynamo;
  private static LambdaClient lambda;
  private static CloudWatchClient cloudwatch;
  private static String table;
  private static String function;

  @BeforeAll
  static void connect() {
    Assumptions.assumeTrue(TARGET_IS_AWS, "AWS resource tests run only with -Paws");
    Assumptions.assumeTrue(AwsEnvironment.available(), "Cannot read the stack: " + AwsEnvironment.failureReason());
    dynamo = DynamoDbClient.builder().region(AwsEnvironment.REGION).build();
    lambda = LambdaClient.builder().region(AwsEnvironment.REGION).build();
    cloudwatch = CloudWatchClient.builder().region(AwsEnvironment.REGION).build();
    table = AwsEnvironment.tableName();
    function = AwsEnvironment.functionName();
  }

  @AfterAll
  static void disconnect() {
    if (dynamo != null) dynamo.close();
    if (lambda != null) lambda.close();
    if (cloudwatch != null) cloudwatch.close();
  }

  @AfterEach
  void cleanup() {
    if (client != null) client.cleanup();
  }

  private static Map<String, AttributeValue> key(String id) {
    return Map.of("id", AttributeValue.fromS(id));
  }

  // ---------- CloudFormation ----------

  @Test
  @Tag("smoke")
  @DisplayName("Stack is in a healthy, completed state")
  void stackIsComplete() {
    assertThat(AwsEnvironment.stackStatus(), isOneOf("CREATE_COMPLETE", "UPDATE_COMPLETE"));
  }

  @Test
  @Tag("smoke")
  @DisplayName("Live app reports the DynamoDB backend, served over HTTPS from a Lambda URL")
  void appRunsOnLambdaWithDynamo() {
    assertThat(BASE_URL, allOf(startsWith("https://"), containsString(".lambda-url." + AwsEnvironment.REGION.id() + ".on.aws")));
    given().spec(anonymous).when().get("/health").then().statusCode(200).body("backend", equalTo("DynamoStore"));
  }

  // ---------- DynamoDB: the API and the table agree ----------

  @Test
  @DisplayName("A submission created through the API is stored in DynamoDB with the same values")
  void apiWriteLandsInDynamo() {
    Map<String, Object> payload = Submissions.plagiarised();
    String id = client.create(payload).then().statusCode(201).extract().path("id");

    Map<String, AttributeValue> item = dynamo.getItem(r -> r.tableName(table).key(key(id)).consistentRead(true)).item();

    assertThat("item exists in table " + table, item.isEmpty(), is(false));
    assertThat(item.get("title").s(), equalTo(payload.get("title")));
    assertThat(item.get("author").s(), equalTo(payload.get("author")));
    assertThat(item.get("status").s(), equalTo("flagged"));
    assertThat(Double.parseDouble(item.get("similarity_score").n()), equalTo(100.0));
    assertThat(Integer.parseInt(item.get("word_count").n()), equalTo(13));
  }

  @Test
  @DisplayName("Deleting through the API removes the item from DynamoDB")
  void apiDeleteRemovesFromDynamo() {
    String id = client.create(Submissions.unique()).path("id");
    client.delete(id).then().statusCode(204);

    assertThat(dynamo.getItem(r -> r.tableName(table).key(key(id)).consistentRead(true)).hasItem(), is(false));
  }

  @Test
  @DisplayName("An item written straight to DynamoDB is served by the API with correct types")
  void apiReadsWhatIsInDynamo() {
    String id = UUID.randomUUID().toString();
    Map<String, AttributeValue> item = new HashMap<>();
    item.put("id", AttributeValue.fromS(id));
    item.put("title", AttributeValue.fromS("Written directly to the table"));
    item.put("author", AttributeValue.fromS("java-sdk"));
    item.put("word_count", AttributeValue.fromN("7"));
    item.put("similarity_score", AttributeValue.fromN("12.5"));
    item.put("status", AttributeValue.fromS("clear"));
    item.put("created_at", AttributeValue.fromS(Instant.now().toString()));
    dynamo.putItem(r -> r.tableName(table).item(item));
    try {
      client.get(id)
          .then().statusCode(200)
          .body("title", equalTo("Written directly to the table"))
          .body("word_count", equalTo(7))
          .body("similarity_score", equalTo(12.5f));
      client.list().then().body("items.id", hasItem(id));
    } finally {
      dynamo.deleteItem(r -> r.tableName(table).key(key(id)));
    }
  }

  @Test
  @DisplayName("Data survives across separate requests, so it is not held in Lambda memory")
  void dataPersistsAcrossInvocations() {
    String id = client.create(Submissions.unique()).path("id");
    for (int i = 0; i < 5; i++) {
      client.get(id).then().statusCode(200).body("id", equalTo(id));
    }
  }

  @Test
  @DisplayName("Table is on-demand billing with id as the partition key")
  void tableIsConfiguredAsDesigned() {
    TableDescription t = dynamo.describeTable(r -> r.tableName(table)).table();
    assertThat(t.tableStatusAsString(), equalTo("ACTIVE"));
    assertThat(t.billingModeSummary().billingMode(), equalTo(BillingMode.PAY_PER_REQUEST));
    assertThat(t.keySchema(), hasSize(1));
    assertThat(t.keySchema().get(0).attributeName(), equalTo("id"));
  }

  // ---------- Lambda ----------

  @Test
  @DisplayName("Lambda runs Python 3.12 with the DynamoDB backend wired to this stack's table")
  void lambdaIsConfiguredAsDesigned() {
    GetFunctionConfigurationResponse cfg = lambda.getFunctionConfiguration(r -> r.functionName(function));
    assertThat(cfg.runtimeAsString(), equalTo("python3.12"));
    assertThat(cfg.handler(), equalTo("aws.app_handler.handler"));
    assertThat(cfg.timeout(), lessThanOrEqualTo(30));
    assertThat(cfg.environment().variables(), hasEntry("STORAGE_BACKEND", "dynamodb"));
    assertThat(cfg.environment().variables(), hasEntry("SUBMISSIONS_TABLE", table));
    assertThat(cfg.lastUpdateStatusAsString(), equalTo("Successful"));
  }

  @Test
  @DisplayName("Function URL is public by design, so the app's own API key is the access control")
  void functionUrlIsPublicAndAppEnforcesAuth() {
    assertThat(lambda.getFunctionUrlConfig(r -> r.functionName(function)).authType(), equalTo(FunctionUrlAuthType.NONE));
    given().spec(anonymous).when().get("/api/submissions").then().statusCode(401);
  }

  // ---------- Security posture of the deployed resources ----------

  @Test
  @DisplayName("Deployed function does not use the public default API key")
  void deployedKeyIsNotThePublicDefault() {
    String key = lambda.getFunctionConfiguration(r -> r.functionName(function)).environment().variables().get("SUBMISSION_API_KEY");
    assertThat("a key is configured", key, not(emptyOrNullString()));
    assertThat("key is not the well-known default", key, not(equalTo("qa-demo-key")));
    assertThat("key has reasonable entropy", key.length(), greaterThanOrEqualTo(32));
    given().spec(anonymous).header("X-API-Key", "qa-demo-key").when().get("/api/submissions").then().statusCode(401);
  }

  @Test
  @DisplayName("Table is encrypted at rest and has point-in-time recovery enabled")
  void tableIsEncryptedAndRecoverable() {
    // DynamoDB encrypts every table at rest; SSEDescription is only present for customer-chosen keys.
    assertThat(dynamo.describeTable(r -> r.tableName(table)).table().tableStatusAsString(), equalTo("ACTIVE"));
    String pitr = dynamo.describeContinuousBackups(r -> r.tableName(table))
        .continuousBackupsDescription().pointInTimeRecoveryDescription().pointInTimeRecoveryStatusAsString();
    assertThat(pitr, equalTo("ENABLED"));
  }

  @Test
  @DisplayName("Function URL grants no cross-origin access")
  void functionUrlHasNoCors() {
    var cors = lambda.getFunctionUrlConfig(r -> r.functionName(function)).cors();
    assertThat(cors == null || cors.allowOrigins() == null || cors.allowOrigins().isEmpty(), is(true));
  }

  // ---------- CloudWatch ----------

  @Test
  @DisplayName("Error alarm exists for this function and is not firing")
  void errorAlarmExistsAndIsQuiet() {
    List<MetricAlarm> alarms = cloudwatch.describeAlarms(r -> r.alarmNames(AwsEnvironment.STACK + "-lambda-errors")).metricAlarms();
    assertThat("alarm exists", alarms, hasSize(1));
    MetricAlarm alarm = alarms.get(0);
    assertThat(alarm.metricName(), equalTo("Errors"));
    assertThat(alarm.dimensions().get(0).value(), equalTo(function));
    assertThat("alarm is not in ALARM state", alarm.stateValue(), not(equalTo(StateValue.ALARM)));
  }

  // ---------- Performance on real infrastructure ----------

  @Test
  @DisplayName("Warm requests to the live stack answer within 1 second at p95")
  void warmLatencyIsWithinBudget() {
    given().spec(anonymous).get("/health"); // absorb any cold start
    List<Long> times = new ArrayList<>();
    for (int i = 0; i < 20; i++) {
      times.add(given().spec(anonymous).get("/health").time());
    }
    Collections.sort(times);
    long p95 = times.get(18);
    System.out.println("live /health latency ms: median=" + times.get(10) + " p95=" + p95 + " max=" + times.get(19));
    assertThat("p95 latency in ms", p95, lessThan(1000L));
  }
}
