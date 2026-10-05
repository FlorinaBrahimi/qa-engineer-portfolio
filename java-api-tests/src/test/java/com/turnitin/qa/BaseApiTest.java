package com.turnitin.qa;

import io.restassured.RestAssured;
import io.restassured.builder.RequestSpecBuilder;
import io.restassured.filter.log.LogDetail;
import io.restassured.http.ContentType;
import io.restassured.specification.RequestSpecification;
import java.net.HttpURLConnection;
import java.net.URL;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeAll;

/**
 * Shared configuration for every API test.
 *
 * <p>Target and credentials come from system properties so the same suite runs against the
 * in-process server, Docker, or the live AWS stack:
 *
 * <pre>mvn test                                   # local app on :5001
 * mvn test -Paws                             # live AWS stack, URL read from CloudFormation
 * mvn test -Dbase.url=https://host -Dapi.key=key</pre>
 *
 * <p>If the target is unreachable the suite is skipped rather than failed, so a missing
 * environment is reported as "skipped", distinct from a genuine regression.
 */
abstract class BaseApiTest {

  /** True when the suite was started with -Paws (or -Dbase.url=aws). */
  static final boolean TARGET_IS_AWS = "aws".equalsIgnoreCase(System.getProperty("base.url"));

  static final String BASE_URL = resolveBaseUrl();
  static final String API_KEY = System.getProperty("api.key", "qa-demo-key");

  /** Authenticated JSON request specification. */
  static RequestSpecification authed;

  /** Unauthenticated specification for negative tests. */
  static RequestSpecification anonymous;

  static SubmissionClient client;

  @BeforeAll
  static void configureRestAssured() {
    Assumptions.assumeTrue(serverIsUp(), "Submission Service not reachable at " + BASE_URL);
    RestAssured.baseURI = BASE_URL;
    RestAssured.enableLoggingOfRequestAndResponseIfValidationFails(LogDetail.ALL);

    anonymous = new RequestSpecBuilder().setContentType(ContentType.JSON).setAccept(ContentType.JSON).build();
    authed = new RequestSpecBuilder().addRequestSpecification(anonymous).addHeader("X-API-Key", API_KEY).build();
    client = new SubmissionClient(authed);
  }

  private static boolean serverIsUp() {
    try {
      HttpURLConnection conn = (HttpURLConnection) new URL(BASE_URL + "/health").openConnection();
      conn.setConnectTimeout(5000);
      conn.setReadTimeout(10000); // allows for a Lambda cold start
      return conn.getResponseCode() == 200;
    } catch (Exception e) {
      return false;
    }
  }

  /** "aws" means: ask CloudFormation for the live URL of the deployed stack. */
  private static String resolveBaseUrl() {
    if (TARGET_IS_AWS) {
      return AwsEnvironment.available() ? stripTrailingSlash(AwsEnvironment.appUrl()) : "http://aws-stack-unavailable.invalid";
    }
    return stripTrailingSlash(System.getProperty("base.url", "http://localhost:5001"));
  }

  private static String stripTrailingSlash(String url) {
    return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
  }
}
