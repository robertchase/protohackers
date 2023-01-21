### had problems with `connection reset by peer` on mac.

at first i thought that the use of `asyncio` was screwing things up,
so i switched to my `spindrift` framework's `network` module to get
closer to the metal. that didn't fix the problem.

then i thought maybe i was hitting an open file limit so i bumped that value
way up. that didn't fix the problem.

i checked logs and decided that the voluminous inbound connection/network traffic
occuring during the `large.test` portion of the check
was being knocked down by the os or firewall or something
(lots of resets).
i tried turning the firewall off. the result was the same.

i decided to go with a google cloud debian instance.
it worked like a charm.
