# Curated Demo Cases

These cases are captured from real Quick Run outputs.

## 1) Streetlight Outage (Queens)

**Prompt**  
A streetlight has been completely out for 7 days at the intersection of Main St and 3rd Ave in Queens. The lamp is directly above the crosswalk by the grocery store, and pedestrians have trouble seeing at night. No other issues are present.

**Key outputs**
- Agency: NYC DOT - Street Lighting
- Urgency: low
- Confidence: 83%
- Human review recommended: false
- Follow-up required: false

**Recommended action**  
Open a streetlight outage work order for NYC DOT Street Lighting for the lamp directly above the crosswalk at the intersection of Main St and 3rd Ave in Queens (adjacent to the grocery store). Dispatch a street lighting crew to inspect and repair (replace lamp/ballast or remediate electrical/pole issues), verify the pole ID and circuit, test nearby fixtures for related outages, and document repairs with photos and notes. If the crew identifies exposed wiring, a damaged pole, or other immediate safety risks, escalate to an emergency response team and notify NYPD for pedestrian/traffic control as needed.

**Justification**  
Street lighting outages are handled by NYC DOT Street Lighting. The report gives a clear location (Main St & 3rd Ave, lamp above crosswalk by grocery store) and notes the light has been out for seven days causing reduced nighttime visibility for pedestrians. While this increases risk, there is no report of an active immediate life-threatening condition, so urgency is low but repair is warranted promptly. The recommended action sends a maintenance crew to inspect and fix the outage and escalate if hazardous conditions are found.

**What it demonstrates**  
Precise civic infrastructure routing with location-aware action planning.

## 2) Trash + Rats (Brooklyn)

**Prompt**  
Overflowing garbage bags have been left on the sidewalk outside 200 Atlantic Ave in Brooklyn for three days. The bags are torn and food waste is visible. Rats were seen around 11pm last night near the trash. This is a recurring issue at this address.

**Key outputs**
- Agency: Department of Sanitation (DSNY) and Department of Health and Mental Hygiene (DOHMH)
- Urgency: low
- Confidence: 90%
- Human review recommended: false
- Follow-up required: false

**Recommended action**  
Dispatch DSNY to 200 Atlantic Ave to remove torn/overflowing garbage bags, collect visible food waste, and perform street cleaning as soon as possible (same-day or next available). Simultaneously refer to DOHMH Rodent Control for inspection and abatement (baiting/trapping) due to the reported rat sighting at ~23:00 and ongoing food attractants. Open a recurring-issue enforcement referral to DSNY to notify the property owner/occupant of sanitation rules and pursue follow-up enforcement if violations continue; request DOHMH follow-up monitoring after abatement. Notify reporter of scheduled pickup/inspection times.

**Justification**  
Torn bags with exposed food waste present an attractant for rodents; rats were observed at the site and the problem has persisted/recurs over multiple days, so both removal of refuse (DSNY) and rodent inspection/abatement (DOHMH) are needed, plus enforcement to address recurring violations.

**What it demonstrates**  
Multi-agency recommendation with recurring-condition handling.

## 3) Pothole Hazard (Manhattan)

**Prompt**  
There is a deep pothole in the middle lane at 78 Broadway in Manhattan near the bus stop. Two cars swerved sharply to avoid it this morning and one vehicle got a flat tire. The pothole is about 40 cm wide and 10 cm deep and is hard to see at night.

**Key outputs**
- Agency: NYC Department of Transportation (DOT) - Street Maintenance/Pothole Repair
- Urgency: low
- Confidence: 90%
- Human review recommended: false
- Follow-up required: false

**Recommended action**  
Dispatch DOT pothole crew to 78 Broadway (middle lane, near bus stop) for immediate inspection and temporary remediation (cold patch or temporary fill) and placement of high-visibility cones/reflective signage to warn drivers at night; schedule permanent repair/resurfacing as soon as practicable; notify NYPD traffic if needed for temporary traffic control until repair is completed.

**Justification**  
Report gives precise location and measurements (~40 cm wide, 10 cm deep) and describes vehicles swerving and one flat tire, indicating an active roadway hazard with collision/damage risk and poor nighttime visibility. DOT pothole crew intervention and temporary traffic warning measures are appropriate to mitigate further incidents.

**What it demonstrates**  
Roadway hazard triage with mitigation instructions.

## 4) Gas Smell Emergency (Queens)

**Prompt**  
Right now there is a strong gas / rotten-egg smell coming from a manhole in front of our building in Queens near 123 Main St. Two people nearby feel dizzy and nauseous. The smell is getting stronger over the last 10 minutes. No fire is visible, but we are worried about immediate danger.

**Key outputs**
- Agency: Emergency Services / Police
- Urgency: high
- Confidence: 75%
- Human review recommended: false
- Follow-up required: false

**Recommended action**  
Escalate immediately to emergency services

**Justification**  
location=Queens, category=safety, evidence_top_agency=DEP, evidence_vote_ratio=1.00, evidence_top_score=0.46

**What it demonstrates**  
Immediate hazard routing with debug-style evidence string preserved.

## 5) Recurring Noise Complaint (Brooklyn)

**Prompt**  
There is a loud party with music and shouting at 2am in Brooklyn every weekend (usually Friday and Saturday nights). It lasts for hours and multiple neighbors cannot sleep. This has been happening for about a month. No violence is reported, but it is disrupting the area repeatedly.

**Key outputs**
- Agency: NYPD
- Urgency: medium
- Confidence: 70%
- Human review recommended: false
- Follow-up required: false

**Recommended action**  
Create noise complaint ticket; advise caller; dispatch non-emergency check if repeated

**Justification**  
time=02:00, recurrence=every weekend, location=Brooklyn, category=noise, evidence_top_agency=NYPD, evidence_vote_ratio=1.00, evidence_top_score=0.68

**What it demonstrates**  
Recurring disturbance handling with evidence-backed routing and medium urgency.
