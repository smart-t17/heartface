Format: 1A

# Heartface API

Heartface api. Base URL path: /api/v1/ . Resources use pagination where applicable (nested resrouces, OTOH, do not
at the moment). Resources below are grouped based on the use (sometimes the main) use, but there will be some overlap
between mobile, admin and web endpoints naturaly. All resource URLs supposed to end with a / (even if they are
accidentally missing below from a few places).


# Group authentication

Authorization is done by passing an authorization header with every request.
The header should look like this:
```
Authorization: Token <key_from_authentication>
```

Where `key_from_authentication` is the key returned
by the authentication endpoints described below. (Note that the `<>` brackets
are not needed.)

## Facebook [/rest-auth/facebook]

### Login/signup [POST]

Login/sign up using an access token acquired from the facebook API. (Accepting auth code is also implemented, but
not set up correctly, so will fail for now.)

+ access_token (string) - provide *either* this or code
+ code (string) - doesn't work at the moment

Response contains a (long-lived, opaque) token and the User object

+ Response 200 (application/json)
```
{
  "key": "4c3b0b0de83d8a2c8143a935830f7714a491417b",
  "user": {
    "id": 2,
    "first_name": "László",
    "last_name": "Márai",
    "username": "consumer",
    "email": "consumer@a.co",
    "age": null,
    "gender": "male",
    "photo": null,
    "description": null,
    "can_charge": true|false,
    "url": "http://heartface.io/api/v1/users/2/",
  }
}
```

## Email/username + password

### Sign up [POST /rest-auth/register]?

### Login [POST /rest-auth/login/]

Login using email or username and password

+ Attributes
  + email|username (string)
  + password (string)

+ Response 200 (application/json)

Response format is the same as with facebook login.


# Group App (web+mobile) endpoints

## Users [/users/]

### Retrieve a list of users [GET]

### Retrieve the profile of a specific user [GET /users/{id}/]

+ Parameters
  + id - id of the user. The special value `me` represents the current
    (logged-in) user.

+ Attributes
  + following (boolean) - shows whether the *requesting* user is following
  this user.

This is also available through /rest-auth/user


### Retrieve own profile [GET /users/me/]
This is also available through /rest-auth/user

### Update own profile [PUT /users/me/]

### Get Stripe ephemeral key (needed for payment) [POST /users/me/stripe_key/]

This creates (hence the POST) and returns a Stripe ephemeral key needed
by the mobile clients during the payment flow to update the customer
information.

+ Attributes
  + api_version (string) - the API version the client uses. Optional. If not provided, defaults


### Follow/unfollow a user [PATCH /users/{id}/]

**NOTE: this isn't implemented now. See below how to do it.**

+ Attributes
  + following (boolean)

### Get the videos of a specific user [/users/{id}/videos/]

We may decide to embed this in the [User] resrouce as well, but that's an optimization that's not necessarily needed
(or wise) at the beginning. Even then, we'll need this endpoint.

### Followers of a specific user [GET /users/{id}/followers/]

Returns a list of User objects

### Follow a user [POST /users/{id}/followers/]

Content of the POST is ignored.

### Unfollow a user [DELETE /users/{id}/followers/]

### List of users who a specific user follows [GET /users/{id}/following/]

Returns a list of User objects

### List of ids of users who the current user follows [GET /users/{id}/following/ids/]

Regardless of the value of `id` it will always return the ID list for
the current user. (Use `me` for id.)

### List of video ids a user has likes [GET /users/{id}/likes/ids]

### Check availability of usernames (for registration) [GET /users/usernames/{username}]

Check if the specifid username exists (response code HTTP/200) or
(if not) available to be registered (response code HTTP/404).

+ Response 200 (application/json)
If username is already taken. TBD: suggestions may be returned here
later on, when needed.

    ```
    {}
    ```

+ Response 404 (application/json)
If username is not associated with any account yet, available for
registration.

## Followers [/followers/]

Followers of the current (logged-in) user.
NOTE: this could be nested under /users/me/followers/ as well.


## Following [/following/]

Users following the current (logged-in) user.
NOTE: this could be nested under /users/me/following/ as well.


NOTE: this could be nested under /users/{id}|me/following as well to have a nicer, more canonical API.
It would allow listing (displaying) who a specific user follows. Not sure if it's needed, might be
needed later.

Mutation operations (POST, DELETE) on this collection are not implemented, because those would be a
less versatile way of handling followings. (Good, when editing as a list, impractical when
following/unfollowing a speficic user e.g. from their profile page.)


## Video [/videos/]

+ Attributes
  + products (array[string])
  + hashtags (array[string])


### Retrieve a list of videos [GET]

### Retrieve a specific video [GET /videos/{id}/]

### Create a new video [POST]

### Create a new video by uploading a video file [POST /videos/upload/]

This is the preferred method. Will create a video and immediately start
uploading the content to the CDN (in the backrgound) and return a video
resource.

### Post (or update) video file for a video resource [PUT /videos/{id}/upload]

NOTE: we may restrict changing/updating the video file for a video object
(other than doing it once after creating the video).

### Modify/edit a video's meta data [PUT /videos/{id}/]

E.g. to change products, hashtags. We can make a separate subresource for for these to allow add/delete operations if
it helps with the mobile development. I.e. add or delete a product from a video individually as opposed to having to
do this via always updating the list of products. E.g. /videos/{id}/products/ . Probably not needed though.

### List of comments for a video [GET /videos/{id}/comments/]

### Post a new comment on a video [POST /videos/{id}/comments/]

### Send a view report / inform the server that the video has been viewed by the user [POST /videos/{id}/views/]

A view report should be sent when at least a predefined length of the video has been watched by
the user. At the moment this is 30%. (Later on we might want to add view position as well where
the playback has finished and only send the report then.) Note that while this can be used to fake
views, the server, at the moment, only counts one view for each user at most, so repeat reports
are ignored.

Content of the POST body is ignored.

## Orders [/orders/]

Orders should not allowed to be deleted through the API even by admins. Access is restricted to own orders for
non-admin users.

### List orders [GET]

### Create an order [POST]

+ Attributes
  + stripe_token (string) - Stripe token to use as a 'source' when creating the charge
  + product (number) - supplier product id to order
  + size (string) - size of the product
  + stripe_token (string) - stripe card token. Only needed (and regarded) if user doesn't
      have a payment method set up yet. (See `can_charge` field on /users/me/)
  + other optional payment data from the stripe mobile SDK - TBD

### Retrieve a specific order [GET /orders/{id}/]

### Modify order [PUT /orders/{id}/]


## Hashtags [/hashtags/]

Can be used to browse by hashtags

### Get an individual hashtag [GET /hashtags/{id}/]

Associated videos will NOT be nested as the list can grow very big and paging is not supported by DRF for nested
resources (and may not be trivial to implement). We'll need a good strategy here. E.g. we might embed a few videos
and provide a paramaterized link for more (this is an optimization that's not necessarily needed at the beninning), or
just use a nested resource link:

### List of videos that belong to this hashtag [GET /hashtags/{id}/videos/]

## Collections [/collections/]

Collections are a set of videos grouped together by the admins/editors.
Each collections has a name and a cover picture. Listing and mutation
operations are not needed.

### Get an individual collection [GET /collections/{id}/]
+ Attributes
  + name (string)
  + picture (string) - url of the (cover) picture
  + videos (array[Video]) - list of videos that belong to this category


## Notifications [/notifications/]

### List notifications [GET]

### Update notification (set read status) [PUT /notifications/{id}/]

+ Attributes
  + read (boolean)

### Register to receive *push* notifications [POST v1/notifications/register/]

In order to receive push notifications the device has to be registered.
This can be done by passing the `player_id` (as received from OneSignal)
and the device type to this endpoint. A user can have multiple
registrations from multiple devices. The registration cannot be (and
doesn't need to be) deleted.

+ Attributes
  + player_id (string) - ID/token received from OneSignal
  + type (string) - type of the device. Can be ios or android.

+ Response 201 (application/json)

## Feed [/feed/]

Get the feed contents. The feed is a read-only resource.

+ Response 200 (application/json)
```
  [
    {
      "type": "video|like|comment|follow",
      "content": {
        // Video or Like or Comment resource
      }
    },
  ]
```

## Recommended videos [/redommended/]

A list of video objects, the recommended videos.

## Discovery [/discovery/]

Content for the discovery screen of the app, containing of edited
recommendations and (later) algorithmically picked ('trending') content
(hashtags and profiles). This is a read-only resource.

Exact Format TBD, but the idea is to collect and wrap all the information that is presented
on the discovery screen of the app, including featured users, hashtags, videos, etc. Here is
an example based on the current understanding (and mobile app design):

+ Response 200 (application/json)
```
  {
    "featured": {
      // A single video object representing the featured video
    },
    "collections": [
      // List of collection objects (without the actual videos, probably)
      {
        "id": "https://..../api/v../collections/collection_id/", // Note, this field may be called url instead
        "name": "collection name",
        "picture": "https://.../url/to/picture",
      },
      {...}
    ],
    "hashtags": [
      // List of trending/featured hashtags
    ],
    "trending": [
      // List of trending users
    ]
  }
```


## Search [/search/]

This endpoint does provide ... search. Search is usually hard to do with REST semantics, so it may look weird.

Search parameters are passed in as query parameters.

+ Parameters
  + q: query string (string, required)
  + topic: where/what to search. (array[enum[string]], required)
    + Members
      + `users`
      + `hashtags`
      + `videos`
      + `products`

Note that initially we'll only implement searching a single topic, because
this is what's needed for the mobile app and this is also what's easy to create
a sane response format for in a way that supports paging.

+ Response 200 (application/json)
```
  {
      "count": 10,
      "next": "https://..../api/v1/search/?q=abc&topic=users&limit=10&offset=10",
      "previous": null,
      "results": [
          // User objects
          { ... },
      ]
  }
```

One way to support multiple topics is not supporting paging in this case, or only
supporting paging for the individual topic (which doesn't make too much sense).
E.g.:

+ Response 200 (application/json)
```
  {
    "users": {
      // A complete, paged resultset included here, as defined above (option 1)
    },
    "hashtags": {
      // ...
    }
  }
```

or without paging:

+ Response 200 (application/json)
```
  {
    "users": [
      // A list of objects included here, i.e. only the "results" key from
      // the single topic example above
    ],
    "hashtags": [
    ]
  }
```

# Data structures
