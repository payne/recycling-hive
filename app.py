import os
from datetime import datetime
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import utilities as helper
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")
DEMO_ID = os.environ.get("DEMO_ID")
DEMO_HIVE = os.environ.get("DEMO_HIVE")

mongo = PyMongo(app)


# Routes
@app.route("/")
def home():
    '''
    Get variables for homepage notifications: whether user is Demo, QueenBee,
    Approved etc and whether they are waiting for any collections to be
    approved
    '''
    try:
        username = session["username"]
        user_id = ObjectId(session["user_id"])
        if user_id == ObjectId(DEMO_ID):
            hive_name = "Demo"
        else:
            hive_name = mongo.db.hives.find_one(
                {"_id": ObjectId(session["hive"])})["name"]
        if mongo.db.hiveMembers.find_one(
                {"_id": user_id, "isQueenBee": True}):
            is_queen_bee = True
        else:
            is_queen_bee = False
        if mongo.db.hiveMembers.find_one(
                {"_id": ObjectId(session["user_id"]), "approvedMember": True}):
            approved_member = True
        else:
            approved_member = False
        if helper.awaiting_approval(user_id):
            awaiting_approval = True
        else:
            awaiting_approval = False
        if helper.get_unapproved_public(user_id):
            public_approval = True
        else:
            public_approval = False
        unapproved_collections = helper.get_unapproved_public(user_id)
        if is_queen_bee:
            unapproved_members = helper.get_unapproved_members()
            first_collections = helper.get_first_collections()
            unapproved_member_collections = helper.get_unapproved_collections()
        else:
            unapproved_members = None
            first_collections = None
            unapproved_member_collections = None
        return render_template("pages/index.html",
                               username=username, hive_name=hive_name,
                               page_id="home", is_queen_bee=is_queen_bee,
                               approved_member=approved_member,
                               awaiting_approval=awaiting_approval,
                               public_approval=public_approval,
                               unapproved_collections=unapproved_collections,
                               unapproved_members=unapproved_members,
                               first_collections=first_collections,
                               unapproved_member_collections=unapproved_member_collections)
    except:
        return render_template(
            "pages/index.html", username=False, page_id="home")


@app.route("/register")
def find_a_hive():
    '''
    List hives that can be joined
    '''
    hives = mongo.db.hives.find()
    if session.get("user"):
        if session["user"] == "demo@demo.com":
            # Remove session variables for Demo login
            helper.pop_variables()
            return render_template("pages/find-a-hive.html", hives=hives)

    return render_template("pages/find-a-hive.html", hives=hives)


@app.route("/register/<hive>", methods=["GET", "POST"])
def register(hive):
    '''
    Add registration details to db if not existing user
    '''
    security_question = mongo.db.hives.find_one(
            {"name": hive})["securityQuestion"]
    hive_id = mongo.db.hives.find_one(
            {"name": hive})["_id"]
    if request.method == "POST":
        existing_user = mongo.db.hiveMembers.find_one(
            {"email": request.form.get("email").lower()})
        if existing_user:
            flash("Email already exists")
            return redirect(url_for("register", hive=hive))
        user = request.form.get("email")
        register = {
            "username": request.form.get("username"),
            "email": user.lower(),
            "password": generate_password_hash(request.form.get("password")),
            "securityQuestion": request.form.get("securityQuestion"),
            "marketing": request.form.get("marketing"),
            "postcode": request.form.get("postcode"),
            "isQueenBee": False,
            "isWorkerBee": False,
            "approvedMember": False,
            "hive": ObjectId(hive_id)
        }
        mongo.db.hiveMembers.insert_one(register)

        helper.set_session_variables(user, "Busy Bee")
        flash("Registration Successful!")
        return redirect(url_for("home"))

    return render_template("pages/auth.html", page_id="register",
                           security_question=security_question, hive=hive)


@app.route("/login", methods=["GET", "POST"])
def login():
    '''
    Check user details match db and assign session variables
    '''
    if session.get("user"):
        if session["user"] == "demo@demo.com":
            helper.pop_variables()
            return render_template("pages/auth.html", page_id="login")
    if request.method == "POST":
        existing_user = mongo.db.hiveMembers.find_one(
            {"email": request.form.get("email").lower()})
        if existing_user:
            if check_password_hash(
                    existing_user["password"], request.form.get("password")):
                user = existing_user["email"]
                user_id = str(mongo.db.hiveMembers.find_one(
                    {"email": user})["_id"])
                if mongo.db.hiveMembers.find_one(
                        {"_id": ObjectId(user_id),
                         "isQueenBee": True}):
                    member_type = "Queen Bee"
                elif mongo.db.hiveMembers.find_one(
                        {"_id": ObjectId(user_id),
                         "isWorkerBee": True}):
                    member_type = "Worker Bee"
                else:
                    member_type = "Busy Bee"
                helper.set_session_variables(user, member_type)
                return redirect(url_for("home"))
            else:
                flash("Incorrect email and/or password")
                return redirect(url_for("login"))
        else:
            flash("Incorrect email and/or password")
            return redirect(url_for("login"))

    return render_template("pages/auth.html", page_id="login")


@app.route("/demo")
def demo():
    '''
    Set demo values for session items
    '''
    session["user"] = "demo@demo.com"
    session["username"] = "Demo User"
    session["user_id"] = str(DEMO_ID)
    session["hive"] = str(DEMO_HIVE)
    session["member_type"] = "Busy Bee"
    return redirect(url_for("home"))


@app.route("/hive-management/<username>")
@helper.queen_bee_required
def hive_management(username):
    '''
    Get values for page requests/management
    '''
    unapproved_members = helper.get_unapproved_members()
    first_collections = helper.get_first_collections()
    unapproved_collections = helper.get_unapproved_collections()
    members = list(mongo.db.hiveMembers.find(
        {"hive": ObjectId(session["hive"])}).sort("username"))
    worker_bees = list(mongo.db.hiveMembers.find(
            {"hive": ObjectId(
                session["hive"]), "isWorkerBee": True}).sort("username"))
    members_location_values = helper.create_unnested_list(
        "collectionLocations")
    locations_dict = list(mongo.db.collectionLocations.aggregate([
            {
             "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {"$project": {
             "hiveMembers": "$hiveMembers.username",
             "hiveMembersID": "$hiveMembers._id",
             "nickname": 1,
             "street": 1,
             "town": 1,
             "postcode": 1,
             "id": 1
             }
             },
            {"$sort": {"hiveMembers": 1}}
            ]))
    members_collection_values = helper.create_unnested_list(
        "itemCollections")
    collections_dict = list(mongo.db.itemCollections.aggregate([
            {
             "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {
             "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
             "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
             },
            },
            {"$unwind": "$itemCategory"},
            {
             "$lookup": {
                "from": "collectionLocations",
                "localField": "locationID",
                "foreignField": "_id",
                "as": "collectionLocations"
             },
            },
            {"$unwind": "$collectionLocations"},
            {"$project": {
             "categoryName": "$itemCategory.categoryName",
             "typeOfWaste": "$recyclableItems.typeOfWaste",
             "hiveMembers": "$hiveMembers.username",
             "hiveMembersID": "$hiveMembers._id",
             "nickname": "$collectionLocations.nickname",
             "street": "$collectionLocations.street",
             "town": "$collectionLocations.town",
             "postcode": "$collectionLocations.postcode",
             "id": 1,
             "conditionNotes": 1,
             "charityScheme": 1
             }
             },
            {"$sort": {"hiveMembers": 1, "categoryName": 1, "typeOfWaste": 1}}
            ]))
    return render_template("/pages/hive-management.html",
                           unapproved_members=unapproved_members,
                           first_collections=first_collections,
                           unapproved_collections=unapproved_collections,
                           members=members,
                           worker_bees=worker_bees,
                           locations_dict=locations_dict,
                           members_location_values=members_location_values,
                           members_collection_values=members_collection_values,
                           collections_dict=collections_dict,
                           page_id="management")


@app.route("/hive-management/delete-member-request/<member_id>")
@helper.queen_bee_required
def delete_member_request(member_id):
    '''
    Delete new member from database
    '''
    mongo.db.hiveMembers.remove({"_id": ObjectId(member_id)})
    flash("Membership request has been successfully deleted")
    return redirect(url_for("hive_management", username=session["username"]))


@app.route("/hive-management/approve-member-request/<member_id>")
@helper.queen_bee_required
def approve_member_request(member_id):
    '''
    Approve new member in database
    '''
    filter = {"_id": ObjectId(member_id)}
    approve = {"$set": {"approvedMember": True}}
    mongo.db.hiveMembers.update(filter, approve)
    flash("Membership request has been successfully approved")
    return redirect(url_for("hive_management", username=session["username"]))


@app.route("/hive-management/delete-private-collection-request\
    /<collection_id>")
@helper.queen_bee_required
def delete_private_collection_request(collection_id):
    '''
    Remove first collection from database
    '''
    mongo.db.firstCollection.remove({"_id": ObjectId(collection_id)})
    flash("Worker Bee request has been successfully deleted")
    return redirect(url_for("hive_management", username=session["username"]))


@app.route("/hive-management/approve-private-collection-request/\
    <collection_id>",
           methods=["GET", "POST"])
@helper.queen_bee_required
def approve_private_collection_request(collection_id):
    '''
    Approve collection and add details to the db
    '''
    if request.method == "POST":
        first_collection = mongo.db.firstCollection.find_one(
            {"_id": ObjectId(collection_id)})
        member_id = first_collection["memberID"]
        new_location = {
            "nickname": first_collection["nickname"],
            "nickname_lower": first_collection["nickname"].lower(),
            "street": first_collection["street"],
            "town": first_collection["town"],
            "postcode": first_collection["postcode"],
            "memberID": ObjectId(member_id)
        }
        mongo.db.collectionLocations.insert_one(new_location)
        location_id = mongo.db.collectionLocations.find_one(
                {"nickname_lower": first_collection["nickname"].lower(
                )})["_id"]
        existing_category = helper.check_existing_category(
            first_collection["categoryName"].lower())
        if existing_category:
            category_id = existing_category["_id"]
        else:
            new_category = {
                "categoryName": first_collection["categoryName"],
                "categoryName_lower": first_collection["categoryName"].lower()
            }
            mongo.db.itemCategory.insert_one(new_category)
            category_id = mongo.db.itemCategory.find_one(
                {"categoryName_lower": first_collection["categoryName"].lower(
                )})["_id"]
        # Check whether type of waste exists and either add or get ID
        existing_type_of_waste = mongo.db.recyclableItems.find_one(
                {"typeOfWaste_lower": first_collection["typeOfWaste"].lower(),
                    "categoryID": category_id})
        if existing_type_of_waste:
            item_id = existing_type_of_waste["_id"]
        else:
            new_item = {
                "typeOfWaste": first_collection["typeOfWaste"],
                "typeOfWaste_lower": first_collection["typeOfWaste"].lower(),
                "categoryID": category_id
            }
            mongo.db.recyclableItems.insert_one(new_item)
            item_id = mongo.db.recyclableItems.find_one(
                {"typeOfWaste_lower": first_collection["typeOfWaste"].lower(
                )})["_id"]
        new_collection = {
            "itemID": item_id,
            "conditionNotes": first_collection["conditionNotes"],
            "charityScheme": first_collection["charityScheme"],
            "memberID": ObjectId(member_id),
            "locationID": ObjectId(location_id),
            "dateAdded": datetime.now().strftime("%d %b %Y")
        }
        mongo.db.itemCollections.insert_one(new_collection)
        mongo.db.firstCollection.remove({"_id": ObjectId(collection_id)})
        filter = {"_id": ObjectId(member_id)}
        is_worker_bee = {"$set": {"isWorkerBee": True}}
        mongo.db.hiveMembers.update(filter, is_worker_bee)
        flash("Worker Bee request has been successfully approved")
        return redirect(url_for("hive_management",
                                username=session["username"]))
    return redirect(url_for("hive_management", username=session["username"]))


@app.route("/hive-management/approve-public-collection-request/\
    <collection_id>", methods=["GET", "POST"])
@helper.queen_bee_required
def approve_public_collection_request(collection_id):
    '''
    Approve public collection and add details to the db
    '''
    if request.method == "POST":
        public_collection = mongo.db.publicCollections.find_one(
            {"_id": ObjectId(collection_id)})
        existing_category = helper.check_existing_category(
            public_collection["categoryName"].lower())
        if existing_category:
            category_id = existing_category["_id"]
        else:
            new_category = {
                "categoryName": public_collection["categoryName"],
                "categoryName_lower": public_collection["categoryName"].lower()
            }
            mongo.db.itemCategory.insert_one(new_category)
            category_id = mongo.db.itemCategory.find_one(
                {"categoryName_lower": public_collection["categoryName"].lower(
                )})["_id"]
        existing_type_of_waste = helper.check_existing_item(
            public_collection["typeOfWaste"].lower(), category_id)
        if existing_type_of_waste:
            item_id = existing_type_of_waste["_id"]
        else:
            new_item = {
                "typeOfWaste": public_collection["typeOfWaste"],
                "typeOfWaste_lower": public_collection["typeOfWaste"].lower(),
                "categoryID": category_id
            }
            mongo.db.recyclableItems.insert_one(new_item)
            item_id = mongo.db.recyclableItems.find_one(
                {"typeOfWaste_lower": public_collection["typeOfWaste"].lower(
                )})["_id"]
        filter = {"_id": ObjectId(collection_id)}
        collection_updates = {"$set": {"itemID": item_id,
                              "approvedCollection": True},
                              "$rename": {"memberID": "addedBy"},
                              "$unset": {"username": "",
                                         "categoryName": "",
                                         "typeOfWaste": ""}}
        mongo.db.publicCollections.update(filter, collection_updates)
        flash("Public Collection has been successfully approved")
        return redirect(url_for("hive_management",
                                username=session["username"]))
    return redirect(url_for("hive_management", username=session["username"]))


@app.route("/profile/<username>")
@helper.login_required
def profile(username):
    '''
    Get details needed for populating profile page
    '''
    user_id = ObjectId(session["user_id"])
    email = session["user"]
    locations = helper.get_user_locations(user_id)
    collections_dict = list(mongo.db.itemCollections.aggregate([
        {"$match": {"memberID": user_id}},
        {
            "$lookup": {
             "from": "hiveMembers",
             "localField": "memberID",
             "foreignField": "_id",
             "as": "hiveMembers"
            },
        },
        {"$unwind": "$hiveMembers"},
        {
            "$lookup": {
             "from": "recyclableItems",
             "localField": "itemID",
             "foreignField": "_id",
             "as": "recyclableItems"
            },
        },
        {"$unwind": "$recyclableItems"},
        {
         "$lookup": {
            "from": "itemCategory",
            "localField": "recyclableItems.categoryID",
            "foreignField": "_id",
            "as": "itemCategory"
         },
        },
        {"$unwind": "$itemCategory"},
        {
            "$lookup": {
             "from": "collectionLocations",
             "localField": "locationID",
             "foreignField": "_id",
             "as": "collectionLocations"
            },
        },
        {"$unwind": "$collectionLocations"},
        {"$project": {
            "categoryName": "$itemCategory.categoryName",
            "typeOfWaste": "$recyclableItems.typeOfWaste",
            "hiveMembers": "$hiveMembers._id",
            "nickname": "$collectionLocations.nickname",
            "street": "$collectionLocations.street",
            "town": "$collectionLocations.town",
            "postcode": "$collectionLocations.postcode",
            "id": 1,
            "conditionNotes": 1,
            "charityScheme": 1
            }
         },
        {"$sort": {"categoryName": 1, "typeOfWaste": 1}}
        ]))
    unapproved_collections = helper.get_unapproved_public(user_id)
    collections_dict_public = list(mongo.db.publicCollections.aggregate(
        [{"$match": {"addedBy": user_id}},
            {
             "$lookup": {
              "from": "recyclableItems",
              "localField": "itemID",
              "foreignField": "_id",
              "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
            "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
            },
            },
            {"$unwind": "$itemCategory"},
            {"$project": {
             "collectionType": 1,
             "categoryName": "$itemCategory.categoryName",
             "typeOfWaste": "$recyclableItems.typeOfWaste",
             "businessName": 1,
             "councilLocation": 1,
             "street": 1,
             "town": 1,
             "county": 1,
             "postcode": 1,
             "id": 1,
             "conditionNotes": 1,
             "charityScheme": 1,
             "dateAdded": 1
             }
             },
            {"$sort": {"dateAdded": -1}}
         ]))
    # Check whether user has submitted first collection for approval
    if helper.awaiting_approval(user_id):
        awaiting_approval = True
    else:
        awaiting_approval = False
    return render_template("/pages/profile.html", user_id=user_id,
                           username=session["username"], email=email,
                           hive=session["hive"],
                           member_type=session["member_type"],
                           locations=locations,
                           collections_dict=collections_dict,
                           collections_dict_public=collections_dict_public,
                           unapproved_collections=unapproved_collections,
                           page_id="profile",
                           awaiting_approval=awaiting_approval)


@app.route("/<route>/profile/edit/<member_id>", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def edit_profile(route, member_id):
    # Post method for editing user details
    if request.method == "POST":
        # check where email already exists in db
        existing_user = mongo.db.hiveMembers.find_one(
            {"_id": {"$ne": ObjectId(member_id)},
                "email": request.form.get("edit-email").lower()}
        )
        if existing_user:
            flash("Email already exists")
            if route == "profile":
                return redirect(url_for(
                    "profile", username=session["username"]))
            elif route == "management":
                return redirect(url_for(
                    "hive_management", username=session["username"]))

        filter = {"_id": ObjectId(member_id)}
        session["username"] = request.form.get("edit-username")
        edit_details = {"$set": {"username": session["username"],
                        "email": request.form.get(
                        "edit-email").lower()}}
        mongo.db.hiveMembers.update(filter, edit_details)
        if route == "profile":
            flash("Your details have been successfully updated")
            return redirect(url_for("profile", username=session["username"]))
        elif route == "management":
            flash("Member's details have been successfully updated")
            return redirect(url_for(
                "hive_management", username=session["username"]))
    return redirect(url_for("profile", username=session["username"]))


@app.route("/<route>/profile/delete/<member_id>")
@helper.login_required
@helper.no_demo
def delete_profile(route, member_id):
    mongo.db.hiveMembers.remove({"_id": ObjectId(member_id)})
    mongo.db.collectionLocations.remove({"memberID": ObjectId(member_id)})
    mongo.db.itemCollections.remove({"memberID": ObjectId(member_id)})
    if route == "profile":
        flash("Your profile has been successfully deleted")
        return redirect(url_for(
            "logout"))
    elif route == "management":
        flash("Member's profile has been successfully deleted")
        return redirect(url_for(
            "hive_management", username=session["username"]))
    return redirect(url_for("profile", username=session["username"]))


@app.route("/add-new-location", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def add_new_location():
    user_id = ObjectId(session["user_id"])
    if request.method == "POST":
        # Check whether nickname already exists
        existing_nickname = mongo.db.collectionLocations.find_one(
            {"memberID": ObjectId(user_id), "nickname_lower": request.form.get(
                "addLocationNickname").lower()})
        if existing_nickname:
            flash("Location already saved under this nickname")
            return redirect(url_for("profile", username=session["username"]))
        new_location = {
                "nickname": request.form.get("addLocationNickname"),
                "nickname_lower": request.form.get(
                    "addLocationNickname").lower(),
                "street": request.form.get("addLocationStreet"),
                "town": request.form.get("addLocationTown"),
                "postcode": request.form.get("addLocationPostcode"),
                "memberID": user_id
            }
        mongo.db.collectionLocations.insert_one(new_location)
        flash("New location added")
        return redirect(url_for("profile", username=session["username"]))

    return redirect(url_for("profile", username=session["username"]))


@app.route("/<route>/edit-location/<location_id>", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def edit_location(route, location_id):
    if request.method == "POST":
        filter = {"_id": ObjectId(location_id)}
        edit_location = {"$set": {"street": request.form.get("editStreet"),
                         "town": request.form.get("editTown"),
                                  "postcode": request.form.get(
                                      "editPostcode")}}
        mongo.db.collectionLocations.update(filter, edit_location)
        if route == "profile":
            flash("Your location has been updated")
            return redirect(url_for(
                "profile", username=session["username"]))
        elif route == "management":
            flash("Member's location has been updated")
            return redirect(url_for(
                "hive_management", username=session["username"]))

    return redirect(url_for("profile", username=session["username"]))


@app.route("/<route>/delete-location/<location_id>")
@helper.login_required
@helper.no_demo
def delete_location(route, location_id):
    mongo.db.collectionLocations.remove({"_id": ObjectId(location_id)})
    mongo.db.itemCollections.remove({"locationID": ObjectId(location_id)})
    if route == "profile":
        flash("Your location has been successfully deleted")
        return redirect(url_for(
            "profile", username=session["username"]))
    elif route == "management":
        flash("Member's location has been successfully deleted")
        return redirect(url_for(
            "hive_management", username=session["username"]))
    return redirect(url_for("profile", username=session["username"]))


@app.route("/add-first-collection", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def add_first_collection():
    user_id = ObjectId(session["user_id"])
    username = session["username"]
    if request.method == "POST":
        if "newItemCategory" in request.form:
            category_name = request.form.get("newItemCategory")
        else:
            category_name = request.form.get("itemCategory")
        if "newTypeOfWaste" in request.form:
            type_of_waste = request.form.get("newTypeOfWaste")
        else:
            type_of_waste = request.form.get("typeOfWaste")
        charityScheme = request.form.get("charityScheme")
        if charityScheme == "":
            charityScheme = "-"
        first_collection = {
            "hive": ObjectId(session["hive"]),
            "memberID": user_id,
            "username": username,
            "nickname": request.form.get("addLocationNickname"),
            "street": request.form.get("addLocationStreet"),
            "town": request.form.get("addLocationTown"),
            "postcode": request.form.get("addLocationPostcode"),
            "categoryName": category_name,
            "typeOfWaste": type_of_waste,
            "conditionNotes": request.form.get("conditionNotes"),
            "charityScheme": charityScheme,
            "dateAdded": datetime.now().strftime("%d %b %Y")
        }
        mongo.db.firstCollection.insert_one(first_collection)
        flash("First collection sent for approval")
        return redirect(url_for("home"))
    return redirect(url_for("add_new_collection"))


@app.route("/add-new-collection")
@helper.login_required
def add_new_collection():
    # Get user ID for locations
    user_id = ObjectId(session["user_id"])
    # Get list of categories for dropdown
    categories = list(mongo.db.itemCategory.find().sort("categoryName"))
    # Get list of all recyclable items for dropdown
    items_dict = list(mongo.db.recyclableItems.aggregate([
        {
            "$lookup": {
             "from": "itemCategory",
             "localField": "categoryID",
             "foreignField": "_id",
             "as": "itemCategory"
            },
        },
        {"$unwind": "$itemCategory"},
        {"$sort": {"typeOfWaste": 1}}
        ]))
    # get user"s location details from db for location card
    locations = helper.get_user_locations(user_id)
    council_collection = list(mongo.db.hives.find(
        {"_id": ObjectId(session["hive"])}))
    # Check whether user has submitted first collection for approval
    if helper.awaiting_approval(user_id):
        awaiting_approval = True
    else:
        awaiting_approval = False
    return render_template("pages/add-collection.html",
                           categories=categories, items_dict=items_dict,
                           locations=locations, hive=session["hive"],
                           council_collection=council_collection,
                           member_type=session["member_type"],
                           awaiting_approval=awaiting_approval)


@app.route("/add-new-collection/private", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def add_private_collection():
    # Get user ID for adding collection
    user_id = ObjectId(session["user_id"])
    if request.method == "POST":
        # Post method for adding a new category and type of waste
        if "newItemCategory" in request.form:
            # Check whether category already exists
            existing_category = helper.check_existing_category(
                request.form.get("newItemCategory").lower())

            if existing_category:
                flash("Category already exists")
                return redirect(url_for("add_new_collection"))

            new_item_category = {
                "categoryName": request.form.get("newItemCategory"),
                "categoryName_lower": request.form.get(
                    "newItemCategory").lower()
            }
            mongo.db.itemCategory.insert_one(new_item_category)
            category_id = mongo.db.itemCategory.find_one(
                    {"categoryName_lower": request.form.get(
                        "newItemCategory").lower()})["_id"]

            # Check whether item already exists
            existing_type_of_waste = mongo.db.recyclableItems.find_one(
                {"typeOfWaste_lower": request.form.get(
                    "newTypeOfWaste").lower(),
                    "categoryID": category_id}
            )
            if existing_type_of_waste:
                flash("Type of Waste already exists for this category")
                return redirect(url_for("add_new_collection"))

            new_type_of_waste = {
                "typeOfWaste": request.form.get("newTypeOfWaste"),
                "typeOfWaste_lower": request.form.get(
                    "newTypeOfWaste").lower(),
                "categoryID": category_id
            }
            mongo.db.recyclableItems.insert_one(new_type_of_waste)
            item_id = mongo.db.recyclableItems.find_one(
                    {"typeOfWaste_lower": request.form.get(
                        "newTypeOfWaste").lower()})["_id"]
            charityScheme = request.form.get("charityScheme")
            if charityScheme == "":
                charityScheme = "-"
            new_collection = {
                "itemID": item_id,
                "conditionNotes": request.form.get("conditionNotes"),
                "charityScheme": charityScheme,
                "memberID": user_id,
                "locationID": mongo.db.collectionLocations.find_one(
                    {"nickname_lower": request.form.get("locationID").lower(),
                        "memberID": user_id})["_id"],
                "dateAdded": datetime.now().strftime("%d %b %Y")
            }
            mongo.db.itemCollections.insert_one(new_collection)
            flash("New collection added")
            return redirect(url_for("get_recycling_collections",
                                    item_id=item_id))
        # Post method for adding new type of waste with existing category
        if "newTypeOfWaste" in request.form:
            # Check whether item already exists
            existing_type_of_waste = mongo.db.recyclableItems.find_one(
                {"typeOfWaste_lower": request.form.get(
                    "newTypeOfWaste").lower(),
                    "categoryID": mongo.db.itemCategory.find_one(
                    {"categoryName_lower": request.form.get(
                        "itemCategory").lower()})["_id"]}
            )
            if existing_type_of_waste:
                flash("Type of Waste already exists for this category")
                return redirect(url_for("add_new_collection"))

            new_type_of_waste = {
                "typeOfWaste": request.form.get("newTypeOfWaste"),
                "typeOfWaste_lower": request.form.get(
                    "newTypeOfWaste").lower(),
                "categoryID": mongo.db.itemCategory.find_one(
                    {"categoryName_lower": request.form.get(
                        "itemCategory").lower()})["_id"]
            }
            mongo.db.recyclableItems.insert_one(new_type_of_waste)
            item_id = mongo.db.recyclableItems.find_one(
                    {"typeOfWaste_lower": request.form.get(
                        "newTypeOfWaste").lower()})["_id"]
            charityScheme = request.form.get("charityScheme")
            if charityScheme == "":
                charityScheme = "-"
            new_collection = {
                "itemID": item_id,
                "conditionNotes": request.form.get("conditionNotes"),
                "charityScheme": charityScheme,
                "memberID": user_id,
                "locationID": mongo.db.collectionLocations.find_one(
                    {"nickname_lower": request.form.get("locationID").lower(),
                        "memberID": user_id})["_id"],
                "dateAdded": datetime.now().strftime("%d %b %Y")
            }
            mongo.db.itemCollections.insert_one(new_collection)
            flash("New collection added")
            return redirect(url_for("get_recycling_collections",
                                    item_id=item_id))
        # Post method for adding new collection with existing type
        # of waste and category
        if "typeOfWaste" in request.form:
            item_id = mongo.db.recyclableItems.find_one(
                    {"typeOfWaste_lower": request.form.get(
                        "typeOfWaste").lower()})["_id"]
            charityScheme = request.form.get("charityScheme")
            if charityScheme == "":
                charityScheme = "-"
            new_collection = {
                "itemID": item_id,
                "conditionNotes": request.form.get("conditionNotes"),
                "charityScheme": charityScheme,
                "memberID": user_id,
                "locationID": mongo.db.collectionLocations.find_one(
                    {"nickname_lower": request.form.get("locationID").lower(),
                        "memberID": user_id})["_id"],
                "dateAdded": datetime.now().strftime("%d %b %Y")
            }
            mongo.db.itemCollections.insert_one(new_collection)
            flash("New collection added")
            return redirect(url_for("get_recycling_collections",
                                    item_id=item_id))


@app.route("/add-new-collection/public", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def add_public_collection():
    user_id = ObjectId(session["user_id"])
    username = session["username"]
    if request.method == "POST":
        if "newItemCategory" in request.form:
            category_name = request.form.get("newItemCategory")
        else:
            category_name = request.form.get("itemCategory")
        if "newTypeOfWaste" in request.form:
            type_of_waste = request.form.get("newTypeOfWaste")
        else:
            type_of_waste = request.form.get("typeOfWaste")
        charityScheme = request.form.get("charityScheme")
        if charityScheme == "":
            charityScheme = "-"
        if request.form.get("localNational") == "local":
            if request.form.get("councilOther") == "council":
                public_collection = {
                 "hive": ObjectId(session["hive"]),
                 "collectionType": "local-council",
                 "username": username,
                 "memberID": user_id,
                 "councilLocation": request.form.get("councilLocation"),
                 "councilLocation_lower": request.form.get(
                     "councilLocation").lower().replace(" ", "_"),
                 "categoryName": category_name,
                 "typeOfWaste": type_of_waste,
                 "conditionNotes": request.form.get("conditionNotes"),
                 "charityScheme": charityScheme,
                 "approvedCollection": False,
                 "dateAdded": datetime.now().strftime("%d %b %Y")
                }
            if request.form.get("councilOther") == "other":
                public_collection = {
                 "hive": ObjectId(session["hive"]),
                 "collectionType": "local-other",
                 "username": username,
                 "memberID": user_id,
                 "businessName": request.form.get("businessName"),
                 "street": request.form.get("businessStreet"),
                 "town": request.form.get("businessTown"),
                 "postcode": request.form.get("businessPostcode"),
                 "categoryName": category_name,
                 "typeOfWaste": type_of_waste,
                 "conditionNotes": request.form.get("conditionNotes"),
                 "charityScheme": charityScheme,
                 "approvedCollection": False,
                 "dateAdded": datetime.now().strftime("%d %b %Y")
                }
        if request.form.get("localNational") == "national":
            if request.form.get("postalDropoff") == "postal":
                public_collection = {
                 "hive": ObjectId(session["hive"]),
                 "collectionType": "national-postal",
                 "username": username,
                 "memberID": user_id,
                 "businessName": request.form.get("businessName"),
                 "street": request.form.get("businessStreet"),
                 "town": request.form.get("businessTown"),
                 "county": request.form.get("businessCounty"),
                 "postcode": request.form.get("businessPostcode"),
                 "categoryName": category_name,
                 "typeOfWaste": type_of_waste,
                 "conditionNotes": request.form.get("conditionNotes"),
                 "charityScheme": charityScheme,
                 "approvedCollection": False,
                 "dateAdded": datetime.now().strftime("%d %b %Y")
                }
            if request.form.get("postalDropoff") == "dropoff":
                public_collection = {
                 "hive": ObjectId(session["hive"]),
                 "collectionType": "national-dropoff",
                 "username": username,
                 "memberID": user_id,
                 "businessName": request.form.get("businessName"),
                 "categoryName": category_name,
                 "typeOfWaste": type_of_waste,
                 "conditionNotes": request.form.get("conditionNotes"),
                 "charityScheme": charityScheme,
                 "approvedCollection": False,
                 "dateAdded": datetime.now().strftime("%d %b %Y")
                }
        mongo.db.publicCollections.insert_one(public_collection)
        flash("Public collection sent for approval")
        return redirect(url_for("add_new_collection"))


@app.route("/<route>/edit-collection/<collection_id>", methods=["GET", "POST"])
@helper.login_required
@helper.no_demo
def edit_collection(route, collection_id):
    if request.method == "POST":
        filter = {"_id": ObjectId(collection_id)}
        charityScheme = request.form.get("editCharity")
        if charityScheme == "":
            charityScheme = "-"
        edit_collection = {"$set":
                           {"conditionNotes": request.form.get("editNotes"),
                            "charityScheme": charityScheme,
                            "locationID": ObjectId(
                                request.form.get("editLocation"))}}
        mongo.db.itemCollections.update(filter, edit_collection)
        if route == "profile":
            flash("Your collection has been updated")
            return redirect(url_for(
                "profile", username=session["username"]))
        elif route == "management":
            flash("Member's collection has been updated")
            return redirect(url_for(
                "hive_management", username=session["username"]))

    return redirect(url_for("profile", username=session["username"]))


@app.route("/<route>/delete-collection/<collection_id>")
@helper.login_required
@helper.no_demo
def delete_collection(route, collection_id):
    mongo.db.itemCollections.remove({"_id": ObjectId(collection_id)})
    if route == "profile":
        flash("Your collection has been successfully deleted")
        return redirect(url_for(
            "profile", username=session["username"]))
    elif route == "management":
        flash("Member's collection has been successfully deleted")
        return redirect(url_for(
            "hive_management", username=session["username"]))
    return redirect(url_for("profile", username=session["username"]))


@app.route("/<route>/delete-public-collection-submission/<collection_id>")
@helper.login_required
@helper.no_demo
def delete_public_collection_submission(route, collection_id):
    mongo.db.publicCollections.remove({"_id": ObjectId(collection_id)})
    if route == "profile":
        flash("Your public collection submission\
            has been successfully deleted")
        return redirect(url_for(
            "profile", username=session["username"]))
    elif route == "management":
        flash("Member's public collection submission\
            has been successfully deleted")
        return redirect(url_for(
            "hive_management", username=session["username"]))
    return redirect(url_for("profile", username=session["username"]))


@app.route("/hive")
@helper.approval_required
def get_recycling_categories():
    # Get categories in private collections
    categories_dict_private = list(mongo.db.itemCollections.aggregate([
            {
             "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {
             "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
             "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
             },
            },
            {"$unwind": "$itemCategory"},
            {"$group": {
             "_id": "$itemCategory._id",
             "categoryName": {"$first": "$itemCategory.categoryName"}
             }
             },
            {"$sort": {"categoryName": 1}}
            ]))
    # Get categories in public collections
    categories_dict_public = list(mongo.db.publicCollections.aggregate([
            {"$match": {"approvedCollection": True, "$or": [{"hive": ObjectId(
                session["hive"])}, {"collectionType": "national-postal"},
                {"collectionType": "national-dropoff"}]}},
            {
             "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
             "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
             },
            },
            {"$unwind": "$itemCategory"},
            {"$group": {
             "_id": "$itemCategory._id",
             "categoryName": {"$first": "$itemCategory.categoryName"}
             }
             },
            {"$sort": {"categoryName": 1}}
            ]))
    # Combine lists
    categories_dict = list(helper.combine_dictionaries(
        categories_dict_private, categories_dict_public))
    categories_dict.sort(key=lambda x: x["categoryName"])
    return render_template(
        "pages/hive-category.html",
        categories_dict=categories_dict,
        page_id="categories")


@app.route("/hive/items/<category_id>")
@helper.approval_required
def get_recycling_items(category_id):
    if category_id == "view-all":
        # Get selected category for dropdown
        selected_category = "Select a category"
        # Get recyclable items that match the selected category for
        # # hexagon headers in private collection
        recycling_items_dict_private = list(
            mongo.db.itemCollections.aggregate([
             {
              "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
              },
             },
             {"$unwind": "$hiveMembers"},
             {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
             {
              "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
              },
             },
             {"$unwind": "$recyclableItems"},
             {"$group": {
              "_id": "$recyclableItems._id",
              "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
              }
              },
             {"$sort": {"typeOfWaste": 1}}
            ]))
        # Get recyclable items that match the selected category for
        # # hexagon headers in public collection
        recycling_items_dict_public = list(
            mongo.db.publicCollections.aggregate([
                {"$match": {"approvedCollection": True,
                 "$or": [{"hive": ObjectId(
                  session["hive"])}, {"collectionType": "national-postal"},
                  {"collectionType": "national-dropoff"}]}},
                {
                 "$lookup": {
                  "from": "recyclableItems",
                  "localField": "itemID",
                  "foreignField": "_id",
                  "as": "recyclableItems"
                 },
                },
                {"$unwind": "$recyclableItems"},
                {"$group": {
                 "_id": "$recyclableItems._id",
                 "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
                 }
                 },
                {"$sort": {"typeOfWaste": 1}}
            ]))
        # Combine lists
        recycling_items_dict = list(helper.combine_dictionaries(
            recycling_items_dict_private, recycling_items_dict_public))
        recycling_items_dict.sort(key=lambda x: x["typeOfWaste"])
    else:
        # Get selected category for dropdown
        selected_category = mongo.db.itemCategory.find_one(
                    {"_id": ObjectId(category_id)})["categoryName"]
        # Get recyclable items that match the selected category for
        # # hexagon headers in private collection
        recycling_items_dict_private = list(
            mongo.db.itemCollections.aggregate([
             {
              "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
              },
             },
             {"$unwind": "$hiveMembers"},
             {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
             {
              "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
              },
             },
             {"$unwind": "$recyclableItems"},
             {"$match": {"recyclableItems.categoryID": ObjectId(category_id)}},
             {"$group": {
              "_id": "$recyclableItems._id",
              "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
              }
              },
             {"$sort": {"typeOfWaste": 1}}
            ]))
        # Get recyclable items that match the selected category for
        # # hexagon headers in public collection
        recycling_items_dict_public = list(
            mongo.db.publicCollections.aggregate([
                {"$match": {"approvedCollection": True,
                 "$or": [{"hive": ObjectId(
                  session["hive"])}, {"collectionType": "national-postal"},
                  {"collectionType": "national-dropoff"}]}},
                {
                 "$lookup": {
                  "from": "recyclableItems",
                  "localField": "itemID",
                  "foreignField": "_id",
                  "as": "recyclableItems"
                 },
                },
                {"$unwind": "$recyclableItems"},
                {"$match": {"recyclableItems.categoryID": ObjectId(
                    category_id)}},
                {"$group": {
                 "_id": "$recyclableItems._id",
                 "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
                 }
                 },
                {"$sort": {"typeOfWaste": 1}}
            ]))
        # Combine lists
        recycling_items_dict = list(helper.combine_dictionaries(
            recycling_items_dict_private, recycling_items_dict_public))
        recycling_items_dict.sort(key=lambda x: x["typeOfWaste"])
    # Get list of categories for dropdown menu
    # Get categories in private collections
    categories_dict_private = list(mongo.db.itemCollections.aggregate([
            {
             "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {
             "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
             "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
             },
            },
            {"$unwind": "$itemCategory"},
            {"$group": {
             "_id": "$itemCategory._id",
             "categoryName": {"$first": "$itemCategory.categoryName"}
             }
             },
            {"$sort": {"categoryName": 1}}
            ]))
    # Get categories in public collections
    categories_dict_public = list(mongo.db.publicCollections.aggregate(
        [{"$match": {"approvedCollection": True,
          "$or": [{"hive": ObjectId(session["hive"])},
                  {"collectionType": "national-postal"},
                  {"collectionType": "national-dropoff"}]}},
            {
             "$lookup": {
                "from": "recyclableItems",
                "localField": "itemID",
                "foreignField": "_id",
                "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
             "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
             },
            },
            {"$unwind": "$itemCategory"},
            {"$group": {
             "_id": "$itemCategory._id",
             "categoryName": {"$first": "$itemCategory.categoryName"}
             }
             },
            {"$sort": {"categoryName": 1}}
         ]))
    # Combine lists
    categories_dict = list(helper.combine_dictionaries(
        categories_dict_private, categories_dict_public))
    categories_dict.sort(key=lambda x: x["categoryName"])
    return render_template(
        "pages/hive-item.html",
        categories_dict=categories_dict,
        recycling_items_dict=recycling_items_dict,
        selected_category=selected_category, page_id="items")


@app.route("/hive/collections/<item_id>")
@helper.approval_required
def get_recycling_collections(item_id):
    if item_id == "view-all":
        # Get selected item for dropdown
        selected_item = "Select an item"
    else:
        # Get selected item for dropdown
        selected_item = mongo.db.recyclableItems.find_one(
                    {"_id": ObjectId(item_id)})["typeOfWaste"]
    # Get list of items for dropdown menu in private collection
    recycling_items_dict_private = list(
        mongo.db.itemCollections.aggregate([
            {
             "$lookup": {
              "from": "hiveMembers",
              "localField": "memberID",
              "foreignField": "_id",
              "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {
             "$lookup": {
              "from": "recyclableItems",
              "localField": "itemID",
              "foreignField": "_id",
              "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {"$group": {
             "_id": "$recyclableItems._id",
             "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
             }
             },
            {"$sort": {"typeOfWaste": 1}}
        ]))
    # Get list of items for dropdown menu in public collection
    recycling_items_dict_public = list(mongo.db.publicCollections.aggregate(
        [{"$match": {"approvedCollection": True,
          "$or": [{"hive": ObjectId(session["hive"])},
                  {"collectionType": "national-postal"},
                  {"collectionType": "national-dropoff"}]}},
            {
             "$lookup": {
              "from": "recyclableItems",
              "localField": "itemID",
              "foreignField": "_id",
              "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {"$group": {
             "_id": "$recyclableItems._id",
             "typeOfWaste": {"$first": "$recyclableItems.typeOfWaste"}
             }
             },
            {"$sort": {"typeOfWaste": 1}}
         ]))
    # Combine lists
    recycling_items_dict = list(helper.combine_dictionaries(
        recycling_items_dict_private, recycling_items_dict_public))
    recycling_items_dict.sort(key=lambda x: x["typeOfWaste"])
    # Create new dictionary of recyclable items and their
    # matching collections from private collection
    collections_dict_private = list(
        mongo.db.itemCollections.aggregate([
         {
          "$lookup": {
            "from": "hiveMembers",
            "localField": "memberID",
            "foreignField": "_id",
            "as": "hiveMembers"
          },
         },
         {"$unwind": "$hiveMembers"},
         {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
         {
          "$lookup": {
            "from": "recyclableItems",
            "localField": "itemID",
            "foreignField": "_id",
            "as": "recyclableItems"
          },
         },
         {"$unwind": "$recyclableItems"},
         {
          "$lookup": {
            "from": "itemCategory",
            "localField": "recyclableItems.categoryID",
            "foreignField": "_id",
            "as": "itemCategory"
          },
         },
         {"$unwind": "$itemCategory"},
         {
          "$lookup": {
            "from": "collectionLocations",
            "localField": "locationID",
            "foreignField": "_id",
            "as": "collectionLocations"
          },
         },
         {"$unwind": "$collectionLocations"},
         {"$project": {
          "categoryName": "$itemCategory.categoryName",
          "typeOfWaste": "$recyclableItems.typeOfWaste",
          "hiveMembers": "$hiveMembers.username",
          "street": "$collectionLocations.street",
          "town": "$collectionLocations.town",
          "postcode": "$collectionLocations.postcode",
          "id": 1,
          "conditionNotes": 1,
          "charityScheme": 1
          }
          }
        ]))
    # Create new dictionary of recyclable items and their
    # matching collections from public collection
    collections_dict_public = list(mongo.db.publicCollections.aggregate(
        [{"$match": {"approvedCollection": True,
          "$or": [{"hive": ObjectId(session["hive"])},
                  {"collectionType": "national-postal"},
                  {"collectionType": "national-dropoff"}]}},
            {
             "$lookup": {
              "from": "recyclableItems",
              "localField": "itemID",
              "foreignField": "_id",
              "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
            "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
            },
            },
            {"$unwind": "$itemCategory"},
            {"$project": {
             "collectionType": 1,
             "categoryName": "$itemCategory.categoryName",
             "typeOfWaste": "$recyclableItems.typeOfWaste",
             "councilLocation": 1,
             "businessName": 1,
             "street": 1,
             "town": 1,
             "county": 1,
             "postcode": 1,
             "id": 1,
             "conditionNotes": 1,
             "charityScheme": 1
             }
             }
         ]))
    return render_template(
        "pages/hive-collection.html",
        recycling_items_dict=recycling_items_dict,
        collections_dict_private=collections_dict_private,
        collections_dict_public=collections_dict_public,
        selected_item=selected_item,
        page_id="collections")


@app.route("/hive/collector/<collector_type>")
@helper.approval_required
def get_recycling_collector(collector_type):
    if collector_type == "view-all":
        # Get selected collector type for dropdown
        selected_collector_type = "Select a Collection Type"
        # Get all private collectors for
        # hexagon headers
        private_collector = list(mongo.db.itemCollections.aggregate([
            {
             "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
             },
            },
            {"$unwind": "$hiveMembers"},
            {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
            {"$group": {
             "_id": "$hiveMembers._id",
             "username": {"$first": "$hiveMembers.username"}
             }
             },
            {"$sort": {"username": 1}}
            ]))
        # Get all local council collectors for hexagon headers
        local_council_collector = list(
                mongo.db.publicCollections.aggregate([
                    {"$match": {"hive": ObjectId(
                        session["hive"]), "approvedCollection": True,
                        "collectionType": "local-council"}},
                    {"$group": {
                     "_id": "$councilLocation_lower",
                     "councilLocation": {"$first": "$councilLocation"}
                     }
                     },
                    {"$sort": {"_id": 1}}
                    ]))
    else:
        # Get selected member type for dropdown
        selected_collector_type = collector_type
        # Get members that match the selected type for
        # # hexagon headers
        if collector_type == "Worker Bee":
            private_collector = list(mongo.db.itemCollections.aggregate([
             {
              "$lookup": {
                "from": "hiveMembers",
                "localField": "memberID",
                "foreignField": "_id",
                "as": "hiveMembers"
              },
             },
             {"$unwind": "$hiveMembers"},
             {"$match": {"hiveMembers.hive": ObjectId(session["hive"])}},
             {"$group": {
              "_id": "$hiveMembers._id",
              "username": {"$first": "$hiveMembers.username"}
              }
              },
             {"$sort": {"username": 1}}
            ]))
            local_council_collector = None
        elif collector_type == "Local Council":
            local_council_collector = list(
                mongo.db.publicCollections.aggregate([
                    {"$match": {"hive": ObjectId(
                        session["hive"]), "approvedCollection": True,
                        "collectionType": "local-council"}},
                    {"$group": {
                     "_id": "$councilLocation_lower",
                     "councilLocation": {"$first": "$councilLocation"}
                     }
                     },
                    {"$sort": {"_id": 1}}
                    ]))
            private_collector = None
    # Get list of members addresses for collection card groups
    private_collector_locations = list(mongo.db.hiveMembers.aggregate([
        {"$match": {"hive": ObjectId(session["hive"])}},
        {
         "$lookup": {
            "from": "itemCollections",
            "localField": "_id",
            "foreignField": "memberID",
            "as": "itemCollections"
         },
        },
        {"$unwind": "$itemCollections"},
        {
         "$lookup": {
            "from": "collectionLocations",
            "localField": "itemCollections.locationID",
            "foreignField": "_id",
            "as": "collectionLocations"
         },
        },
        {"$unwind": "$collectionLocations"},
        {"$group": {
             "_id": "$collectionLocations._id",
             "memberID": {"$first": "$_id"},
             "street": {"$first": "$collectionLocations.street"},
             "town": {"$first": "$collectionLocations.town"},
             "postcode": {"$first": "$collectionLocations.postcode"}
             }
         },
        {"$sort": {"nickname": 1}}
        ]))
    # Create new dictionary of members and their collections
    private_collector_dict = list(mongo.db.hiveMembers.aggregate([
        {"$match": {"hive": ObjectId(session["hive"])}},
        {
         "$lookup": {
            "from": "itemCollections",
            "localField": "_id",
            "foreignField": "memberID",
            "as": "itemCollections"
         },
        },
        {"$unwind": "$itemCollections"},
        {
         "$lookup": {
            "from": "recyclableItems",
            "localField": "itemCollections.itemID",
            "foreignField": "_id",
            "as": "recyclableItems"
         },
        },
        {"$unwind": "$recyclableItems"},
        {
         "$lookup": {
            "from": "itemCategory",
            "localField": "recyclableItems.categoryID",
            "foreignField": "_id",
            "as": "itemCategory"
         },
        },
        {"$unwind": "$itemCategory"},
        {
         "$lookup": {
            "from": "collectionLocations",
            "localField": "itemCollections.locationID",
            "foreignField": "_id",
            "as": "collectionLocations"
         },
        },
        {"$unwind": "$collectionLocations"},
        {"$project": {
         "categoryName": "$itemCategory.categoryName",
         "typeOfWaste": "$recyclableItems.typeOfWaste",
         "locationID": "$collectionLocations._id",
         "street": "$collectionLocations.street",
         "town": "$collectionLocations.town",
         "postcode": "$collectionLocations.postcode",
         "conditionNotes": "$itemCollections.conditionNotes",
         "charityScheme": "$itemCollections.charityScheme"
         }
         },
        {"$sort": {"categoryName": 1, "typeOfWaste": 1}}
        ]))
    local_council_collector_dict = list(mongo.db.publicCollections.aggregate(
        [{"$match": {"hive": ObjectId(
            session["hive"]), "approvedCollection": True,
                     "collectionType": "local-council"}},
            {
             "$lookup": {
              "from": "recyclableItems",
              "localField": "itemID",
              "foreignField": "_id",
              "as": "recyclableItems"
             },
            },
            {"$unwind": "$recyclableItems"},
            {
            "$lookup": {
                "from": "itemCategory",
                "localField": "recyclableItems.categoryID",
                "foreignField": "_id",
                "as": "itemCategory"
            },
            },
            {"$unwind": "$itemCategory"},
            {"$project": {
             "_id": "$councilLocation_lower",
             "collectionType": 1,
             "categoryName": "$itemCategory.categoryName",
             "typeOfWaste": "$recyclableItems.typeOfWaste",
             "councilLocation": 1,
             "id": 1,
             "conditionNotes": 1,
             "charityScheme": 1
             }
             }
         ]))
    return render_template(
        "pages/hive-collector.html",
        selected_collector_type=selected_collector_type,
        private_collector=private_collector,
        private_collector_locations=private_collector_locations,
        private_collector_dict=private_collector_dict,
        local_council_collector=local_council_collector,
        local_council_collector_dict=local_council_collector_dict,
        page_id="collector")


@app.route("/contact")
def contact():

    return render_template("pages/contact.html")


@app.route("/logout")
def logout():
    # remove user from session cookies
    flash("Log Out Successful!")
    helper.pop_variables()
    return redirect(url_for("home"))


@app.route("/faqs")
def faqs():

    return render_template("pages/faq.html")


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template("pages/404.html"), 404


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=os.environ.get("DEBUG"))
