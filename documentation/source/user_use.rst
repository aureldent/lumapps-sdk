Users
=====

The SDK includes a helper to easily manipulate the users.

To list all users of your Lumapps plateform
------------------------------------------------

.. code-block:: python 

    from lumapps.helpers import user

    api = ... # previously obtained
    users = user.list(api)

    for usr_dict, usr_obj in users:
        print(usr_obj.uid)

To create a user
----------------

Save a user by provinding an `email`, a `first_name` and a `last_name`.

.. code-block:: python

    from lumapps.helpers.user import User

    api = ... # previously obtained
    usr = User(
          api,
          email="email",
          representation ={"firstName":"first_name","lastName":"last_name"},
    )
    success, errors = usr.save()
    print(success)

