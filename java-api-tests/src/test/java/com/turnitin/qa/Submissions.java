package com.turnitin.qa;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Test data factory: unique payloads for isolation, fixed fixtures for exact outcomes. */
final class Submissions {

  private Submissions() {}

  /** A payload that shares no five-word shingle with the corpus, so it always scores 0. */
  static Map<String, Object> unique() {
    String u = UUID.randomUUID().toString().substring(0, 8);
    Map<String, Object> m = new HashMap<>();
    m.put("title", "Java paper " + u);
    m.put("author", "author-" + u);
    m.put("text", "A unique sentence " + u + " written for this run that matches nothing in the known corpus.");
    return m;
  }

  static Map<String, Object> unique(String field, Object value) {
    Map<String, Object> m = unique();
    m.put(field, value);
    return m;
  }

  /** Text copied verbatim from the corpus: expected 100% similarity, status flagged. */
  static Map<String, Object> plagiarised() {
    Map<String, Object> m = unique();
    m.put("text", "The mitochondria is the powerhouse of the cell and produces energy through respiration");
    return m;
  }

  /** Half corpus, half original: expected strictly between 0 and 100. */
  static Map<String, Object> partialOverlap() {
    Map<String, Object> m = unique();
    m.put("text", "To be or not to be that is the question whether tis nobler in the mind to suffer, "
        + "and in my own words I think this means choosing courage.");
    return m;
  }
}
