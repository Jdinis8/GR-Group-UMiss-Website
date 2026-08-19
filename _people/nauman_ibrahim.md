---
# Copy this file to _people/first-last.md, then remove `published: false`.
name: Nauman Ibrahim
last_name: Ibrahim
# Allowed roles: full-professor, associate-professor, assistant-professor,
# postdoc, phd-student, masters-student, undergraduate, staff, affiliate
role: staff
role_label: Research Associate
photo: /assets/images/people/nibrahim.jpeg
tagline: Working on the kinematics of Causal Set Theory -- a theory that imagines spacetime to be a locally finite, partially ordered set. Specifically interested in building the analog of the Weyl tensor.
research:
  - Causal Set Theory
  - Alternate theories of gravity
email: naumanibrahimsh@protonmail.com
website: https://sniafrmpk.github.io/
#olemiss_profile: https://olemiss.edu/profiles/your-webid.php
orcid: 0009-0004-5716-840X
# Optional but recommended when OpenAlex has duplicate ORCID records.
#openalex_id: A1234567890
# Optional safeguard for a contaminated OpenAlex author record: orcid or physics
publication_filter: orcid
# Optional comma-separated OpenAlex work IDs that should bypass the filter.
#publication_include: W1234567890, W0987654321
#inspire: https://inspirehep.net/authors/1234567
#cv: /assets/files/first-last-cv.pdf
---

My research centers on constructing a Weyl tensor analog for causal sets — locally finite partially ordered sets meant to represent the underlying discrete structure of spacetime. Our approach rests on the fact that geodesic deviation in a spacetime depends on curvature. Applying this to causal sets first requires generating causal sets that are not conformally flat. We did this by developing a criterion for determining, from their coordinates, whether two points in a gravitational wave spacetime are causally related; a causal set is then obtained by sprinkling points at random (Poisson process) and applying this criterion to each pair.

A second challenge is that the discrete analog of a geodesic in a causal set is usually taken to be a longest chain, but unlike continuum geodesics, these are not unique: the collection of longest chains between two points can be pictured as a "thick tube." This thickness introduces noise into any separation measurement, so reliably estimating the separation between two tubes requires precisely characterizing the thickness. We did this for causal sets sprinkled into Minkowski spacetime, numerically finding that the tube's width decreases weakly with density but grows strongly with the height of the interval. The exact growth exponent is known analytically only for $d=2$; we have found it for higher dimensions as well.

Assuming this result carries over to gravitational-wave causal sets, we showed that the simplest definition of deviation — a single separation measurement at the interval's midpoint — would require on the order of $10^8$ elements to overcome the thickness noise, which is computationally inaccessible. This has prompted us to develop alternate strategies: either redefining deviation to use more of the available information, or sensing curvature by means other than geodesic deviation.

Apart from this kinematic program, I have also explored action-based formulations of classical dynamics, motivated by the absence of a natural Hamiltonian in causal sets. This raises the question of whether there are theories for which specifying initial data on a spatial hypersurface is insufficient, and data must instead be specified over a spacetime \emph{volume}.
