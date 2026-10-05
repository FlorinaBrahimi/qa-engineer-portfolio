package com.turnitin.qa;

import static io.restassured.RestAssured.given;

import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Thin client over the submissions API. Tests call these methods instead of repeating
 * paths and headers, so an endpoint change is a one-line fix here.
 *
 * <p>Also tracks every id it creates so {@link #cleanup()} can delete them after a test,
 * keeping the shared environment tidy when tests run in parallel or against AWS.
 */
final class SubmissionClient {

  static final String SUBMISSIONS = "/api/submissions";

  private final RequestSpecification spec;
  private final List<String> createdIds = new ArrayList<>();

  SubmissionClient(RequestSpecification spec) {
    this.spec = spec;
  }

  Response create(Map<String, ?> payload) {
    Response response = given().spec(spec).body(payload).post(SUBMISSIONS);
    if (response.statusCode() == 201) {
      createdIds.add(response.path("id"));
    }
    return response;
  }

  Response createRaw(String body) {
    return given().spec(spec).body(body).post(SUBMISSIONS);
  }

  Response get(String id) {
    return given().spec(spec).get(SUBMISSIONS + "/" + id);
  }

  Response list() {
    return given().spec(spec).get(SUBMISSIONS);
  }

  Response delete(String id) {
    createdIds.remove(id);
    return given().spec(spec).delete(SUBMISSIONS + "/" + id);
  }

  void cleanup() {
    for (String id : new ArrayList<>(createdIds)) {
      given().spec(spec).delete(SUBMISSIONS + "/" + id);
    }
    createdIds.clear();
  }
}
