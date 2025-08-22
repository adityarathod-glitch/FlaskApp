from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client, Client
import os


app = Flask(__name__)
app.secret_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"


SB_URL = "https://pflybbvywvukylqnhjqw.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"

sb: Client = create_client(SB_URL, SB_KEY)


def normalize_path(path):
    """Normalize path by removing leading/trailing slashes and ensuring consistency"""
    if not path:
        return ""
    return path.strip("/")


def get_breadcrumbs(current_folder):
    """Generate breadcrumb navigation from current folder path"""
    if not current_folder:
        return [{"name": "Root", "path": ""}]
    
    breadcrumbs = [{"name": "Root", "path": ""}]
    parts = current_folder.split("/")
    current_path = ""
    
    for part in parts:
        if part:  # Skip empty parts
            current_path = f"{current_path}/{part}" if current_path else part
            breadcrumbs.append({"name": part, "path": current_path})
    
    return breadcrumbs


@app.route("/")
def index():
    bucket = request.args.get("bucket", "my-bucket")
    folder = normalize_path(request.args.get("folder", ""))

    contents = []
    try:
        options = {"limit": 100, "offset": 0}
        if folder:
            options["prefix"] = folder + "/"

        res = sb.storage.from_(bucket).list(folder, options)
        data = res if isinstance(res, list) else res.get("data", [])

        for obj in data:
            if not isinstance(obj, dict) or not obj.get("name"):
                continue
            
            # Skip the current folder itself and .keep files
            if obj["name"] == folder or obj["name"].endswith(".keep"):
                continue

            # Determine full path
            if folder:
                full_path = f"{folder}/{obj['name']}"
            else:
                full_path = obj["name"]

            if obj.get("metadata") is None:
                # It's a folder
                contents.append({
                    "name": obj["name"],
                    "type": "folder",
                    "path": full_path,
                    "size": 0
                })
            else:
                # It's a file
                contents.append({
                    "name": obj["name"],
                    "type": "file",
                    "path": full_path,
                    "size": obj.get("metadata", {}).get("size", 0)
                })

    except Exception as err:
        flash(f"Error listing contents: {err}")

    # Generate breadcrumbs for navigation
    breadcrumbs = get_breadcrumbs(folder)

    return render_template("index.html",
                           contents=contents,
                           bucket_name=bucket,
                           current_folder=folder,
                           breadcrumbs=breadcrumbs)


@app.route("/upload/<bucket>", methods=["POST"])
def upload_file(bucket):   
    file = request.files.get("file")
    folder = normalize_path(request.form.get("folder", ""))

    if not file:
        flash("No file selected.")
        return redirect(url_for("index", bucket=bucket, folder=folder))

    try:
        if folder:
            path = f"{folder}/{file.filename}"
        else:
            path = file.filename
            
        res = sb.storage.from_(bucket).upload(path, file.read())

        if isinstance(res, dict) and res.get("error"):
            flash(f"Upload failed: {res['error']['message']}")
        else:
            flash(f"Uploaded '{file.filename}' successfully.")
    except Exception as err:
        flash(f"Unexpected error: {err}")

    return redirect(url_for("index", bucket=bucket, folder=folder))


@app.route("/create_folder/<bucket>", methods=["POST"])
def create_folder(bucket):   
    name = request.form.get("folder_name", "").strip()
    parent = normalize_path(request.form.get("parent_folder", ""))

    if not name:
        flash("Folder name required.")
        return redirect(url_for("index", bucket=bucket, folder=parent))

    try:
        if parent:
            folder_path = f"{parent}/{name}"
        else:
            folder_path = name
            
        # Create a .keep file to establish the folder
        keep_file_path = f"{folder_path}/.keep"
        res = sb.storage.from_(bucket).upload(keep_file_path, b"")

        if isinstance(res, dict) and res.get("error"):
            flash(f"Error creating folder: {res['error']['message']}")
        else:
            flash(f"Folder '{name}' created successfully.")
    except Exception as err:
        flash(f"Error creating folder: {err}")

    return redirect(url_for("index", bucket=bucket, folder=parent))


@app.route("/delete_file/<bucket>")
def delete_file(bucket):   
    path = request.args.get("path")
    folder = normalize_path(request.args.get("folder", ""))

    if not path:
        flash("File path required.")
        return redirect(url_for("index", bucket=bucket, folder=folder))

    try:
        res = sb.storage.from_(bucket).remove([path])
        if isinstance(res, dict) and res.get("error"):
            flash(f"Delete failed: {res['error']['message']}")
        else:
            flash(f"Deleted '{os.path.basename(path)}' successfully.")
    except Exception as err:
        flash(f"Error deleting file: {err}")

    return redirect(url_for("index", bucket=bucket, folder=folder))


@app.route("/delete_folder/<bucket>")
def delete_folder(bucket):   
    folder_path = request.args.get("path")
    parent = normalize_path(request.args.get("parent", ""))

    if not folder_path:
        flash("Folder path required.")
        return redirect(url_for("index", bucket=bucket, folder=parent))

    try:
        # First, list all files in the folder
        res = sb.storage.from_(bucket).list(folder_path, {"limit": 1000})
        items = res if isinstance(res, list) else res.get("data", [])
        
        # Collect all files to delete (including nested files)
        to_delete = []
        
        # Add the .keep file
        to_delete.append(f"{folder_path}/.keep")
        
        # Add all files in the folder
        for item in items:
            if isinstance(item, dict) and item.get("name"):
                file_path = f"{folder_path}/{item['name']}"
                to_delete.append(file_path)

        if to_delete:
            # Remove all files
            result = sb.storage.from_(bucket).remove(to_delete)
            if isinstance(result, dict) and result.get("error"):
                flash(f"Folder delete failed: {result['error']['message']}")
            else:
                folder_name = os.path.basename(folder_path)
                flash(f"Folder '{folder_name}' deleted successfully.")
        else:
            flash("Folder is empty, nothing to delete.")
            
    except Exception as err:
        flash(f"Error deleting folder: {err}")

    return redirect(url_for("index", bucket=bucket, folder=parent))


@app.route("/copy_file/<bucket>", methods=["GET", "POST"])
def copy_file(bucket):   
    path = request.args.get("path")
    folder = normalize_path(request.args.get("folder", ""))

    if request.method == "GET":
        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        default_name = f"copy_of_{name}{ext}"
        
        if folder:
            default_path = f"{folder}/{default_name}"
        else:
            default_path = default_name
            
        return render_template("copy_move.html",
                               action="Copy",
                               file_path=path,
                               bucket=bucket,
                               folder=folder,
                               default_path=default_path)

    new_path = request.form.get("new_path", "").strip()
    if not new_path:
        flash("New path required.")
        return redirect(url_for("index", bucket=bucket, folder=folder))

    try:
        content = sb.storage.from_(bucket).download(path)
        if isinstance(content, dict) and content.get("error"):
            flash(f"Download failed: {content['error']['message']}")
        else:
            res = sb.storage.from_(bucket).upload(new_path, content)
            if isinstance(res, dict) and res.get("error"):
                flash(f"Copy failed: {res['error']['message']}")
            else:
                flash(f"File copied to '{new_path}' successfully.")
    except Exception as err:
        flash(f"Error copying: {err}")

    return redirect(url_for("index", bucket=bucket, folder=folder))


@app.route("/move_file/<bucket>", methods=["GET", "POST"])
def move_file(bucket):   
    path = request.args.get("path")
    folder = normalize_path(request.args.get("folder", ""))

    if request.method == "GET":
        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        default_name = f"moved_{name}{ext}"
        
        if folder:
            default_path = f"{folder}/{default_name}"
        else:
            default_path = default_name
            
        return render_template("copy_move.html",
                               action="Move",
                               file_path=path,
                               bucket=bucket,
                               folder=folder,
                               default_path=default_path)

    new_path = request.form.get("new_path", "").strip()
    if not new_path:
        flash("New path required.")
        return redirect(url_for("index", bucket=bucket, folder=folder))

    try:
        content = sb.storage.from_(bucket).download(path)
        if isinstance(content, dict) and content.get("error"):
            flash(f"Download failed: {content['error']['message']}")
            return redirect(url_for("index", bucket=bucket, folder=folder))

        uploaded = sb.storage.from_(bucket).upload(new_path, content)
        if isinstance(uploaded, dict) and uploaded.get("error"):
            flash(f"Move failed: {uploaded['error']['message']}")
            return redirect(url_for("index", bucket=bucket, folder=folder))

        deleted = sb.storage.from_(bucket).remove([path])
        if isinstance(deleted, dict) and deleted.get("error"):
            flash(f"File moved but original not deleted: {deleted['error']['message']}")
        else:
            flash(f"File moved to '{new_path}' successfully.")
    except Exception as err:
        flash(f"Error moving: {err}")

    return redirect(url_for("index", bucket=bucket, folder=folder))


@app.route("/download/<bucket>")
def download_file(bucket):  
    path = request.args.get("path")
    if not path:
        flash("File path required.")
        return redirect(url_for("index", bucket=bucket))

    try:
        res = sb.storage.from_(bucket).create_signed_url(path, 3600)
        if isinstance(res, dict) and res.get("error"):
            flash(f"Download link error: {res['error']['message']}")
        else:
            url = res.get("signedURL") if isinstance(res, dict) else None
            if url:
                return redirect(url)
            flash("Could not generate download link.")
    except Exception as err:
        flash(f"Error downloading: {err}")

    folder = normalize_path(os.path.dirname(path))
    return redirect(url_for("index", bucket=bucket, folder=folder))


@app.route("/create_bucket", methods=["POST"])
def create_bucket():   
    name = request.form.get("bucket_name", "").strip()
    if not name:
        flash("Bucket name required.")
    else:
        flash("Bucket creation must be done in Supabase dashboard.")
    return redirect(url_for("index"))


@app.route("/list_buckets")
def list_buckets():   
    try:
        flash("Listing buckets only available via Supabase dashboard.")
    except Exception as err:
        flash(f"Error listing buckets: {err}")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)