// ALR4's synthetic check: reads one file the page serves and fails when the age of its
// data, the time since its `data_instant`, is over the threshold, or when the file
// cannot be read or parsed. synthetic_check.tf puts `const CONFIG = {...}` before this
// script, with the file's URL and the threshold in seconds, because a k6 script
// receives no variables from Terraform. It fetches the public file only and sends
// nothing else.

import http from "k6/http";
import { check } from "k6";

export default function () {
  const response = http.get(CONFIG.url);

  // A file that is not JSON, or has no `data_instant`, leaves the age unknown, and an
  // unknown age is a failure.
  let ageS = Infinity;
  try {
    const instantMs = Date.parse(response.json("data_instant"));
    if (!Number.isNaN(instantMs)) {
      ageS = (Date.now() - instantMs) / 1000;
    }
  } catch (error) {
    ageS = Infinity;
  }

  check(response, {
    "the file is read": (r) => r.status === 200,
    "the data is not older than the threshold": () => ageS <= CONFIG.max_age_s,
  });
}
