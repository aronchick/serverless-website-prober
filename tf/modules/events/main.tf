

locals {
    shuttles_to_test_in_file = csvdecode(file("${path.module}/estuary_prober_shuttles_to_test.csv"))
    estuary_prober_events = [for s in local.shuttles_to_test_in_file : {"host" = "${s.shuttle}", "timeout": 10, "prober": "estuary_prober", "event_suffix": "${s.event_suffix}"}]
}

locals {
    cids_to_test_in_file = csvdecode(file("${path.module}/cid_prober_cids_to_test.csv"))
    cid_prober_events = [for c in local.cids_to_test_in_file : {"cid" = "${c.cid}", "timeout": 10, "prober": "cid_prober", "event_suffix": "${c.data_to_test}"}]
}

locals {
    // Flatten probably unnecessary
    event_output = flatten(concat(local.estuary_prober_events, local.cid_prober_events))
}