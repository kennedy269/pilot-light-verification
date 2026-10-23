# Decision record: why Texas

**2026-08-13. Claude's recommendation: start in the Denver metro. I reversed it the same day.**

The first plan put the product in Denver, where I live, so I could meet buyers in person. I told
Claude that proximity wasn't a requirement, and with that argument gone the choice came down to
whether the data existed.

It didn't in Colorado. I couldn't verify any feed of pending liquor-licence applications there,
and Denver doesn't appear among the 20 US metros with the most new restaurant openings. Texas
publishes pending applications statewide through an open API, updated the same day. When I
checked the next day, 9 of the 10 sources I wanted covered the whole state, with Fort Worth's
building permits as the one city-level exception.

Licensing data is state-level and catches every opening in a metro, while permit data is
city-level and only enriches what licensing has already found. So the licence application became
the trigger, and every other source joins onto it through the rules in `pilot_light/verify.py`.

Fort Worth has the best permit data in Texas, live and updated hourly, but its city limits held 15
of the 106 pending applications in the Dallas-Fort Worth area, about five new projects a month.
That is too few for a subscription, so the territory stayed at the metro level.
