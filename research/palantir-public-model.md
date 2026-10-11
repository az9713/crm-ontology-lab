# Palantir Ontology — public model shape

Research date: 2026-10-10. Purpose: the exact public shape of the Palantir Foundry Ontology metadata model and runtime API, so a local imitation can match it. Every field below comes from a fetched public source. Items not confirmed are marked **UNVERIFIED**.

## Sources

- **SDK** — Palantir's open-source generated Python SDK, `palantir/foundry-platform-python`, branch `develop`, commit `ec852badbdaeca5479b1880fd890d9717d2d8615` (2026-09-25). Pydantic models read with a static `ast` parse; names below are the camelCase wire names.
  - https://raw.githubusercontent.com/palantir/foundry-platform-python/develop/foundry_sdk/v2/ontologies/models.py
  - https://raw.githubusercontent.com/palantir/foundry-platform-python/develop/foundry_sdk/v2/core/models.py (CORE)
  - Resource files in the same folder: `action.py`, `query.py`, `ontology_object.py`, `ontology_object_set.py`, `linked_object.py`, `object_type.py`, `action_type.py`, `ontology_interface.py` (RES)
- **DOCS** — https://www.palantir.com/docs/foundry/ (pages named per section).
- **API** — https://www.palantir.com/docs/foundry/api/v2/

## A. Ontology and object type (SDK)

```
OntologyV2: apiName, displayName, description, rid
OntologyFullMetadata:
  ontology: OntologyV2
  objectTypes:             {ObjectTypeApiName: ObjectTypeFullMetadata}
  actionTypes:             {ActionTypeApiName: ActionTypeV2}
  actionTypesFullMetadata: {ActionTypeApiName: ActionTypeFullMetadata}   # only if includeActionTypeFullMetadata=true
  queryTypes:              {VersionedQueryTypeApiName: QueryTypeV2}
  interfaceTypes:          {InterfaceTypeApiName: InterfaceType}
  sharedPropertyTypes:     {SharedPropertyTypeApiName: SharedPropertyType}
  branch?:                 BranchMetadata
  valueTypes:              {ValueTypeApiName: OntologyValueType}

ObjectTypeFullMetadata:
  objectType: ObjectTypeV2
  linkTypes: [LinkTypeSideV2]
  implementsInterfaces: [InterfaceTypeApiName]
  implementsInterfaces2: {InterfaceTypeApiName: ObjectTypeInterfaceImplementation}
  sharedPropertyTypeMapping: {SharedPropertyTypeApiName: PropertyApiName}

ObjectTypeV2:
  apiName, displayName, status: ReleaseStatus, description?, pluralDisplayName,
  icon: BlueprintIcon{color (hex), name (Blueprint icon name), type:'blueprint'},
  primaryKey: PropertyApiName, properties: {PropertyApiName: PropertyV2}, rid,
  titleProperty: PropertyApiName, visibility?: NORMAL|PROMINENT|HIDDEN,
  aliases?: [str], datasources?: [ObjectTypeDatasource]

ReleaseStatus (CORE) = ACTIVE | ENDORSED | EXPERIMENTAL | DEPRECATED

ObjectTypeDatasource: rid, definition: one of
  dataset{datasetRid, branch?, propertyMapping: {PropertyApiName: PropertyTypeMappingInfo}}
  table{tableRid, branch?, propertyMapping} | stream{streamRid, branch?, propertyMapping}
  restrictedView{restrictedViewRid, propertyMapping} | direct{directSourceRid, propertyMapping}
  editsOnly{}            # no backing data; all properties set only by Actions; incompatible with any other datasource
  timeSeries{timeSeriesSyncRid, properties} | mediaSetView{mediaSetRid, mediaSetViewRid, properties}
  geotimeSeries{geotimeSeriesIntegrationRid, properties} | unsupported{unsupportedType, properties}

PropertyTypeMappingInfo = column{column} | struct{...} | editOnly{}
  # editOnly: permissioned to the tabular datasource, but populated only through Actions

Object instance (OntologyObjectV2) = {PropertyApiName: value}
  reserved keys confirmed in SDK docstrings: __primaryKey, __apiName, __rid
```

Naming rules (DOCS https://www.palantir.com/docs/foundry/object-link-types/create-object-type/):
- Object type API name: PascalCase, starts uppercase, alphanumeric, 1–100 characters.
- Property API name: camelCase, 1–100 characters.
- Reserved words not permitted, for example `ontology`, `object`, `property`.
- "A single datasource can only be used to back one object type."
- Primary key must be unique and deterministic. Primary key and title key must not be empty.
- Conflicts: the troubleshooting section of the same page permits underscores in API names. The SDK docstring for `ObjectTypeApiName` says "camelCase format". Both conflict with the PascalCase rule above.

## B. Property (SDK, CORE)

```
PropertyV2:
  description?, displayName?, dataType: ObjectPropertyType, rid,
  status?: PropertyTypeStatus, visibility?: NORMAL|PROMINENT|HIDDEN,
  valueTypeApiName?, valueFormatting?, typeClasses?: [{kind, name}],
  dataConstraints?: {nullability?: NULLABLE|NOT_NULLABLE}
    # "Null values may still be observed for objects that are not present in the datasource mapping."

PropertyTypeStatus: {type:'active'} | {type:'experimental'} | {type:'example'}
                  | {type:'deprecated', message, deadline, replacedBy?}

ObjectPropertyType type strings:
  date, string, byte, double, geopoint, geotimeSeriesReference, integer, float, geoshape,
  long, boolean, cipherText{defaultCipherChannel?}, marking{markingType?}, attachment,
  mediaReference, timeseries{itemType}, short,
  vector{dimension, supportsSearchWith:[{value?: COSINE_SIMILARITY|DOT_PRODUCT|EUCLIDEAN_DISTANCE}], embeddingModel?},
  decimal{precision?, scale?}, timestamp,
  array{subType, reducers:[{direction, field?}]},
  struct{structFieldTypes:[{apiName, rid, dataType, typeClasses?}], mainValue?}
```

JSON value encoding (SDK `DataValue` docstring): Date = ISO 8601 local date string; Decimal = string (`"2.718281828"`); Long = string (`"58319870951433"`); Integer, Double, Float, Byte = number; Boolean = boolean; Array = array.

Primary key and title key by base type (DOCS https://www.palantir.com/docs/foundry/object-link-types/properties-overview/):

| Base type | Primary key | Title key |
|---|---|---|
| String, Integer, Short | Yes | Yes |
| Date, Timestamp, Boolean, Byte, Long | Discouraged | Yes |
| Float, Double, Decimal, Geopoint, Cipher, Array | No | Yes |
| Vector, Struct, Geoshape, Marking, Media, Time series, Attachment | No | No |

Base-type rules (DOCS https://www.palantir.com/docs/foundry/object-link-types/base-types/):
- Arrays cannot contain null elements.
- A struct cannot be nested, and a struct field cannot be an array.
- Vector and Time series cannot be in arrays. Map and Binary are not valid base types.

## C. Link type (SDK, DOCS)

```
LinkTypeSideV2:
  apiName, displayName, status: ReleaseStatus,
  objectTypeApiName,                 # the linked (target) object type
  cardinality: ONE | MANY,
  foreignKeyPropertyApiName?,        # the foreign key ON THIS (source) object type
  linkTypeRid
```

Direction confirmed by the API docs example (https://www.palantir.com/docs/foundry/api/v2/ontologies-v2-resources/object-types/list-outgoing-link-types): `GET .../objectTypes/Flight/outgoingLinkTypes` returns `{"apiName": "originAirport", "objectTypeApiName": "Airport", "cardinality": "ONE", "foreignKeyPropertyApiName": "originAirportId"}`. So `objectTypeApiName` is the linked (target) type, and the foreign key is on the requested (source) type.

SDK docstring: "`foreignKeyPropertyApiName` is the API name of the foreign key on this object type. If absent, the link is either a m2m link or the linked object has the foreign key and this object type has the primary key."

- The API has no join-table field. The join datasource of a many-to-many link is not visible in the public metadata.
- Foreign keys support one-to-one and many-to-one. "the one-to-one cardinality is not enforced."
- Many-to-many uses a join-table datasource with columns that match the primary keys of the two object types. "A column can only be mapped to one primary key."
- Object-backed links put an intermediary object type between the two types, with a many-to-one link on each side.
- Link API name: lowercase-first, 1–100 characters. A datasource already backing a link type gives `Phonograph2:DatasetAndBranchAlreadyRegistered`. (https://www.palantir.com/docs/foundry/object-link-types/create-link-type/)
- "Links between object types across different Ontologies are not supported." (https://www.palantir.com/docs/foundry/object-link-types/link-types-overview/)
- Link type API names are unique only within an object type (SDK `ObjectTypeLinkTypeApiNameMapping` docstring).

## D. Action type (SDK, DOCS)

```
ActionTypeV2:
  apiName, description?, displayName?, status: ReleaseStatus,
  parameters: {ParameterId: ActionParameterV2}, rid,
  operations: [LogicRule],           # summary only, no argument mappings
  toolDescription?                   # "intended for tool use contexts, such as AI agents"

ActionParameterV2:
  displayName, description?, dataType: ActionParameterType, required: bool, typeClasses?,
  validation?: {defaultValidation: {allowedValues?: ParameterAllowedValues, arraySize?{gte?, lte?}}}

ActionParameterType:
  date, string, double, integer, geoshape, long, boolean, marking, attachment, mediaReference,
  geohash, vector, decimal, timestamp, scenarioReference, array{subType},
  object{objectApiName, objectTypeApiName}, objectSet{objectApiName?, objectTypeApiName?},
  struct{fields:[{name, fieldType, required}]}, interfaceObject{interfaceTypeApiName?}, objectType

ParameterAllowedValues:
  oneOf{options:[{displayName, value}], otherValuesAllowed}
  range{gt?, gte?, lt?, lte?}        # each bound is ParameterConstraintValue:
                                     #   static{value} | parameterLength{...} | parameterValue{...}
  text{gte?, lte?, regex?, configuredFailureMessage?}   # regex uses Elasticsearch regex semantics
  datetime{gt?, gte?, lt?, lte?} | attachment{maxSizeBytes?} | valueType{apiName, rid, versionId}
  markdown{gte?, lte?} | mustBeEmpty
```

Two rule unions exist. Only the second holds the parameter-to-property mappings.

```
operations: [LogicRule]   (summary)
  createObject{objectTypeApiName} | modifyObject{objectTypeApiName} | deleteObject{objectTypeApiName}
  createLink | deleteLink {linkTypeApiNameAtoB, linkTypeApiNameBtoA, aSideObjectTypeApiName, bSideObjectTypeApiName}
  createInterfaceObject | modifyInterfaceObject | deleteInterfaceObject {interfaceTypeApiName}
  applyScenario{scenarioParameter, objectTypeApiNames, linkTypes}

ActionTypeFullMetadata: {actionType: ActionTypeV2, fullLogicRules: [ActionLogicRule]}
ActionLogicRule:
  createObject{objectTypeApiName, propertyArguments: {PropertyApiName: LogicRuleArgument}, structPropertyArguments}
  modifyObject{objectToModify: ParameterId, propertyArguments, structPropertyArguments}
  createOrModifyObject{objectTypeApiName, ...} | createOrModifyObjectV2{objectToModify, ...}
  deleteObject{objectToDelete}
  createLink | deleteLink {linkTypeApiName, sourceObject: ParameterId, targetObject: ParameterId}
  createInterfaceLink | deleteInterfaceLink {interfaceTypeApiName, interfaceLinkTypeApiName, sourceObject, targetObject}
  createInterface{interfaceTypeApiName, objectType, sharedPropertyArguments, structPropertyArguments}
  modifyInterface{interfaceObjectToModify, sharedPropertyArguments, structPropertyArguments}
  function{functionRid, functionVersion, functionInputValues: {FunctionParameterName: LogicRuleArgument}}
  batchedFunction{objectSetRidInputName, functionRule} | applyScenario{...}

LogicRuleArgument:
  currentTime | currentUser | staticValue{value} | parameterId{parameterId}
  objectParameterPropertyValue{parameterId, propertyTypeApiName}
  interfaceParameterPropertyValue{parameterId, sharedPropertyTypeRid}
  synchronousWebhookOutput{webhookOutputParamName}
  uniqueIdentifier{linkId?}   # same linkId => same generated UUID across rules
StructFieldArgument: structParameterFieldValue | structListParameterFieldValue {parameterId, structParameterFieldApiName}
```

Rule facts (DOCS https://www.palantir.com/docs/foundry/action-types/rules/):
- Create link and delete link are for many-to-many links only. A foreign-key link changes through the modify-object rule.
- A function rule must be the only rule: "no other rule may be configured."
- An action cannot delete an object before it is added, modify an object before it is added, or create the same object twice.
- Logic rules only copy values (parameter, static, current user/time, UUID). Any computed value needs a function rule.
- Webhook, notification and schedule are side-effect rules in the docs. They are **not** `LogicRule` or `ActionLogicRule` variants in the public API. The only API traces are the search predicates `HasWebhookActionTypesQueryV2` and `HasNotificationActionTypesQueryV2`.

Submission criteria (DOCS https://www.palantir.com/docs/foundry/action-types/submission-criteria/):
- **No public metadata schema.** Only the evaluation result is public (section H).
- Three condition templates: Current user, Parameter, Execution context.
- Single-value operators: `is`, `is not`, `matches`, `is less than`, `is greater than or equals`.
- Multi-value operators: `includes`, `includes any`, `is included in`, `each is`, `each is not`.
- Logical operators nest and need all, any, or no conditions to pass. Each root-level condition has its own failure message.
- Attachment and object set parameters are not supported.
- **UNVERIFIED wording:** the fetch tool summarized this page, so operator names may not be word-for-word.

## E. Interface and shared property type (SDK)

```
SharedPropertyType: rid, apiName (lowerCamelCase), displayName, description?, dataType,
                    valueTypeApiName?, valueFormatting?, typeClasses?

InterfaceType:
  rid, apiName (UpperCamelCase), displayName, description?,
  properties:     {SharedPropertyTypeApiName: InterfaceSharedPropertyType}
  allProperties:  {...including extended interfaces}
  propertiesV2:   {InterfacePropertyApiName: InterfacePropertyType}
  allPropertiesV2:{InterfacePropertyApiName: ResolvedInterfacePropertyType}   # ResolvedInterfacePropertyType shape UNVERIFIED
  extendsInterfaces, allExtendsInterfaces, implementedByObjectTypes,
  links / allLinks: {name: InterfaceLinkType}

InterfaceSharedPropertyType (type:'interfaceSharedPropertyType'):
  rid, apiName, displayName, description?, dataType, valueTypeApiName?, valueFormatting?,
  required: bool, typeClasses?
InterfacePropertyType = interfaceSharedPropertyType{...}
  | interfaceDefinedPropertyType{rid, apiName, displayName, description?, dataType, valueTypeApiName?, requireImplementation, typeClasses?}
InterfaceLinkType: rid, apiName, displayName, description?,
  linkedEntityApiName: objectTypeApiName{apiName} | interfaceTypeApiName{apiName},
  cardinality: ONE|MANY, required: bool

ObjectTypeInterfaceImplementation:
  apiName?, rid?, properties: {SharedPropertyTypeApiName: PropertyApiName},
  propertiesV2: {InterfacePropertyApiName: impl}, links: {InterfaceLinkTypeApiName: [LinkTypeApiName]},
  actionTypes: {InterfaceActionTypeConstraintApiName: ActionTypeApiName}
impl = localPropertyImplementation{propertyApiName} | structImplementation{mapping}
     | structFieldImplementation{structFieldOfProperty{propertyApiName, structFieldApiName}}
     | reducedPropertyImplementation{implementation}
```

## F. Object set (SDK)

```
base{objectType} | interfaceBase{interfaceType, includeAllBaseObjectProperties?}
static{objects: [ObjectRid]} | reference{reference: ObjectSetRid}
filter{objectSet, where} | union | intersect | subtract {objectSets}
searchAround{objectSet, link} | interfaceLinkSearchAround{objectSet, interfaceLink}
withProperties{objectSet, derivedProperties} | asType{entityType, objectSet} | asBaseObjectTypes{objectSet}
methodInput{} | nearestNeighbors{objectSet, propertyIdentifier, numNeighbors, similarityThreshold?, query}
```

## G. Filters and aggregation (SDK)

Leaf filters take `field?` or `propertyIdentifier?` (not both), plus a value:

```
eq, gt, gte, lt, lte, contains {value} | in {value: [...]} | isNull {value: bool}
startsWith (deprecated alias of containsAllTermsInOrderPrefixLastTerm), regex, wildcard {value: str}
containsAllTerms, containsAnyTerm {value, fuzzy?: bool}
containsAllTermsInOrder, containsAllTermsInOrderPrefixLastTerm {value}
interval{rule} | relativeDateRange{relativeStartTime?, relativeEndTime?, timeZoneId}
withinDistanceOf, withinBoundingBox, withinPolygon, intersectsBoundingBox, intersectsPolygon,
doesNotIntersectBoundingBox, doesNotIntersectPolygon {value}
geoShapeV2{geometry, spatialFilterMode: INTERSECTS|DISJOINT|WITHIN|CONTAINS}
and | or {value: [...]} | not {value}

propertyIdentifier: property{apiName} | structField{propertyApiName, structFieldApiName}
  | titleProperty | primaryKeyProperty | propertyWithLoadLevel{propertyIdentifier, loadLevel}
```

```
SearchObjectsRequestV2: where?, orderBy?{orderType?: fields|relevance, fields: [{field, direction?: str}]},
                        pageSize?, pageToken?, select, selectV2?, excludeRid?, snapshot?, ...
  response: {data, nextPageToken?, totalCount}
  note: SearchOrderingV2.direction is a plain string, not the ASC/DESC enum.

AggregateObjectsRequestV2: aggregation: [...], where?, groupBy: [...], accuracy?: REQUIRE_ACCURATE|ALLOW_APPROXIMATE
  aggregation: count{name?, direction?}
             | min|max|sum|avg|approximateDistinct|exactDistinct {field?|propertyIdentifier?, name?, direction?: ASC|DESC}
             | approximatePercentile{..., approximatePercentile}
  groupBy: exact{maxGroupCount?, defaultValue?, includeNullValues?} | fixedWidth{fixedWidth}
         | ranges{ranges: [{startValue, endValue}]} | duration{value, unit: MILLISECONDS..YEARS}
  response: {excludedItems?, accuracy, data: [{group: {key: value}, metrics: [{name, value}]}]}
```

## H. Apply action (SDK; endpoint page https://www.palantir.com/docs/foundry/api/v2/ontologies-v2-resources/actions/apply-action)

```
POST /api/v2/ontologies/{ontology}/actions/{action}/apply
  query: branch, transactionId, scenarioRid, sdkPackageRid, sdkVersion
ApplyActionRequestV2:
  parameters: {ParameterId: value | null}
  options?: {mode?: VALIDATE_ONLY | VALIDATE_AND_EXECUTE, returnEdits?: ALL | ALL_V2_WITH_DELETIONS | NONE}
SyncApplyActionResponseV2: operationId?, validation?: ValidateActionResponseV2, edits?
ValidateActionResponseV2:
  result: VALID | INVALID
  submissionCriteria: [{configuredFailureMessage?, result}]
  parameters: {ParameterId: {result, evaluatedConstraints, required, defaultValue?}}
  evaluatedConstraints types: oneOf{options, otherValuesAllowed}, range, arraySize,
    stringLength{lt?, lte?, gt?, gte?}, stringRegexMatch{regex, configuredFailureMessage?},
    objectPropertyValue, objectQueryResult, groupMember, unevaluable, struct, array
edits:
  {type:'edits', edits: [addObject | modifyObject | deleteObject {primaryKey, objectType}
                        | addLink | deleteLink {linkTypeApiNameAtoB, linkTypeApiNameBtoA, aSideObject, bSideObject}],
   addedObjectCount, modifiedObjectsCount, deletedObjectsCount, addedLinksCount, deletedLinksCount}
  | {type:'largeScaleEdits', editedObjectTypes}
applyBatch: {options?{returnEdits?}, requests: [{parameters}]}
```

**Conflict:** in the SDK, `parameters` is inside `validation`. The example response on the docs page puts `parameters` beside `validation`.

## I. Queries and value types (SDK)

```
QueryTypeV2: apiName, description?, displayName?, parameters: {id: {description?, dataType, required}},
             output: QueryDataType, rid, version, typeReferences
POST /v2/ontologies/{ontology}/queries/{queryApiName}/execute  {parameters} -> {value}
OntologyValueType: apiName, displayName, description?, rid, status?: ACTIVE|DEPRECATED, fieldType, version, constraints
  constraints: struct, regex, array, length, ranges, rid, uuid, enum, unsupported
```

## Runtime endpoints (RES, all under `/v2/ontologies/{ontology}`)

GET:
- `objectTypes`, `objectTypes/{objectType}`, `objectTypes/{objectType}/fullMetadata`
- `objectTypes/{objectType}/outgoingLinkTypes[/{linkType}]`
- `objects/{objectType}`, `objects/{objectType}/{primaryKey}`
- `objects/{objectType}/{primaryKey}/links/{linkType}[/{linkedObjectPrimaryKey}]`
- `actionTypes[/{actionType}]`, `interfaceTypes[/{interfaceType}]`, `objectSets/{objectSetRid}`

POST:
- `objects/{objectType}/search|aggregate|count`
- `objectSets/loadObjects|aggregate|createTemporary|loadLinks|loadObjectsMultipleObjectTypes|loadObjectsOrInterfaces`
- `interfaces/{interfaceType}/search|aggregate`
- `actions/{action}/apply|applyBatch|applyWithOverrides|applyBatchWithOverrides`
- `actionTypes/search`, `objectTypes/{objectType}/editsHistory`

## J. Indexing and edits (DOCS)

- Funnel indexes from datasources and from Action edits. Incremental indexing is on by default. (https://www.palantir.com/docs/foundry/object-backend/overview/)
- OSv1 (Phonograph) will be unavailable after 2026-06-30. (same page)
- Limits (same page): 10,000 objects edited per Action; 2000 properties per object type; default Search Around limit 100,000 objects.
- Edits go to a "Funnel-managed queue". Funnel flushes them periodically into Foundry datasets and builds a merged dataset. The merge runs on a new datasource transaction, or "every 6 hours" if there are edits. (https://www.palantir.com/docs/foundry/object-edits/how-edits-applied/)
- Two conflict strategies, set per object type, OSv2 only:
  - "Apply user edits" — the default. Edits always win.
  - "Apply most recent value" — needs a UTC timestamp property. A date property does not work.
- Edit-only properties always take the edit. (same page)
- If a source row goes away, the object goes away. If the row comes back, the old edits apply again. An object last created by a user edit stays. (same page)
- **UNVERIFIED:** community posts say strategies can be set per input datasource and call "most recent value" a limited beta. The posts were not opened. (https://community.palantir.com/t/introducing-conflict-resolution-strategies-for-ontology-user-edits-and-datasource-updates-ga/346)

## Not confirmed

- OSDK and `osdk-ts` sources were not read. Client-side object-set and action shapes there are UNVERIFIED; the API models above are the wire shape.
- Submission-criteria metadata schema: not in the public API.
- Webhook, notification and schedule rule schemas: not in the public API.
- The `__title` reserved key: no match in the SDK.
- Exact submission-criteria operator wording (page was summarized by the fetch tool).
- Types not expanded: `DerivedPropertyDefinition`, `IntervalQueryRule`, `PropertyValueFormattingRule`, `NearestNeighborsQuery`, `BatchReturnEditsMode`, `ResolvedInterfacePropertyType`, `ParameterLengthConstraintValue`, `ParameterValueConstraintValue`.
- A join-table field in the API metadata: none found.
- Action parameter "constraints" as a definition schema: only `validation.defaultValidation` and the runtime evaluated constraints are public.
- Difference between ReleaseStatus `ENDORSED` and `ACTIVE`: no source gives it.
