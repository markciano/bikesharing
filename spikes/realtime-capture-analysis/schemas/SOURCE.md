# Official GBFS JSON Schemas — source and pin

Used by the analysis script for metric 1f (compliance) of the realtime capture analysis plan.

| Item | Value |
|---|---|
| Repository | <https://github.com/MobilityData/gbfs-json-schema> |
| Commit (pinned) | `2e974fd51ae1db9c8006c97375d53e0b882cfedf` |
| Commit date | 2026-08-14 ("feat: Validate conditional presence of station/vehicle feeds in gbfs.json (#208)") |
| Downloaded | 2026-10-05, as the repository tarball of that commit (`gh api repos/MobilityData/gbfs-json-schema/tarball/<commit>`) |
| Copied | Folders `v2.3/` and `v3.0/` and `LICENSE` from the repository root, unchanged |
| Licence | Apache License 2.0 (declared by the repository; the `LICENSE` file at the pinned commit is the Apache 2.0 text). The repository has no `NOTICE` file |
| Used for | AMBici declares GBFS 2.3 (`v2.3/`); Bicing declares GBFS 3.0 (`v3.0/`) |

Not copied: `v1.0`–`v2.2`, `v3.1-RC3`, `models/`, `testFixtures/`.

To update, replace the commit, re-download, recompute the hashes and record the new commit here and in the analysis output.

## SHA-256 of the copied files

```text
cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30  LICENSE
c11e2b0af2869a07414aa6b59d2919094f6d10f5d0ddfc203008c49cea1986af  v2.3/free_bike_status.json
89bc729e29674d5e99e876a41f390fbf10d3817db977c9e58700a1a9fdb4a2f4  v2.3/gbfs.json
4b4e4ef34aac9c6f31a799ef226cd90fb9f8469dc72715c92b043fdf860cfa2c  v2.3/gbfs_versions.json
dc9039a7e5151980cd01795a2420c84e98b684fedb2df6d68adbec08a74add06  v2.3/geofencing_zones.json
0048a8388113ef6bb37113cb83d0c0123bdddbb8fff7071d0fcf6931ed426090  v2.3/station_information.json
10ed322ab4b912fe65d1dd897acc031265c39787e1b44fe2af709dacece9c32c  v2.3/station_status.json
e63da2c7b412f535bd00dfe2577a078af8e60fc45e9787b850a9c185d0b17623  v2.3/system_alerts.json
e9b88c35b81e5193e3d94626d5e15ac26ba39d94263030ec6d1d635957bd892b  v2.3/system_calendar.json
ba6ce2bfa423144c76e01c60026003cf04f75173757b647cf5ab3d25208d5c83  v2.3/system_hours.json
2de079814a3681da50de11f1e2f8720c46fc739c2ae53cd33d4b49461ac47888  v2.3/system_information.json
2f15378612e42ef9a27cd2cb10eef49ba993e5e262eace63b2010052a9c58ba5  v2.3/system_pricing_plans.json
5a2102ae763b90753a864ad39fb2f546f373f74913fcd8475b558a78d4e1921d  v2.3/system_regions.json
aac8bb1bb4e20a5bdf2ea13020552ef337d6468feb238a0da55c5dcbc5d0cb9c  v2.3/vehicle_types.json
e4aa487a0d4e3e33689336a423c2f3ad396e59e6d87a01c07151db5dd601a8e1  v3.0/gbfs.json
caa4c8d24a02bb140b38839e4db09c12e8b7f891b804242341e65f061ea8ad8c  v3.0/gbfs_versions.json
c8b9745ca3d064b5a40c0ecce46b172e927d8b5c0025666c71b36af4a3481a01  v3.0/geofencing_zones.json
8274d25cb31ef5fe43ce32494c24f0c884839f084cb1075055a2d2c104ac3698  v3.0/manifest.json
67d2e3c0eb05176633b5cfef58afef3797b466aeb3d9c43b9e212a59b19bdc21  v3.0/station_information.json
6b92b869d1ed048f7850b86cd9fb517b2ef387ccd0303357a6eba6296234f550  v3.0/station_status.json
d0ec1ec422513d072b5aa1593d09011821dd519886c666ccea53ac4179d6e323  v3.0/system_alerts.json
a8f8ef5c9f734a6df2cdbdc017c3a1264570b1db2073300b4b88d5da8b31106b  v3.0/system_information.json
a088d819fa48ce253f2645b66af6e1bb4d780929977b9aa738ee8b4c02184e13  v3.0/system_pricing_plans.json
fa7f6f50f7c53471f7f984032492032a29277b7714e90721d3052e9a45d14bd8  v3.0/system_regions.json
48d0a7c1785ab4278a969f727ea56d464a839450caa241bfd50a7306a277d8c7  v3.0/vehicle_status.json
8135804aeaa0b4116d3fbd2feefb8bd1a7472104091273baeed91a5887f831b5  v3.0/vehicle_types.json
```
