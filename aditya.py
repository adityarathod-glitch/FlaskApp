from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client, Client
import os


app = Flask(__name__)
app.secret_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"


SB_URL = "https://pflybbvywvukylqnhjqw.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"
SB_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTc1ODA3NiwiZXhwIjoyMDcxMzM0MDc2fQ.qUraO4YsMUl3sfUf6x5jzojCrWqLR3-lW_7QpfTkny4"


sb: Client = create_client(SB_URL, SB_KEY)
sb_admin: Client = create_client(SB_URL, SB_SERVICE_KEY)


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
        if part:  
            current_path = f"{current_path}/{part}" if current_path else part
            breadcrumbs.append({"name": part, "path": current_path})
    
    return breadcrumbs


def get_buckets():
    """Get list of all buckets"""
    try:
        res = sb_admin.storage.list_buckets()
        if isinstance(res, list):
            return res
        elif isinstance(res, dict):
            return res.get("data", [])
        else:
            return list(res) if res else []
    except Exception as e:
        print(f"Error fetching buckets: {e}")
        return []


def is_public_bucket(bucket_name):
    """Check if a bucket is public by examining its configuration"""
    try:
        buckets = get_buckets()
        for bucket in buckets:
            name = bucket.name if hasattr(bucket, 'name') else bucket.get('name') if isinstance(bucket, dict) else str(bucket)
            if name == bucket_name:
                
                if hasattr(bucket, 'public'):
                    return bucket.public
                elif isinstance(bucket, dict):
                    return bucket.get('public', False)
        return False
    except Exception as e:
        print(f"Error checking bucket publicity: {e}")
        return False


def get_client_for_bucket(bucket_name):
    """Get appropriate client based on bucket type"""
    if is_public_bucket(bucket_name):
        return sb_admin  
    return sb  


@app.route("/")
def index():
    bucket = request.args.get("bucket", "my-bucket")
    folder = normalize_path(request.args.get("folder", ""))

    
    raw_buckets = get_buckets()
    buckets = []
    for bucket_obj in raw_buckets:
        if hasattr(bucket_obj, 'name'):
            buckets.append({
                "name": bucket_obj.name,
                "public": getattr(bucket_obj, 'public', False)
            })
        elif isinstance(bucket_obj, dict):
            buckets.append({
                "name": bucket_obj.get("name", "Unknown"),
                "public": bucket_obj.get("public", False)
            })
        else:
            buckets.append({
                "name": str(bucket_obj),
                "public": False
            })

    contents = []
    try:
        
        client = get_client_for_bucket(bucket)
        
        options = {"limit": 100, "offset": 0}
        if folder:
            options["prefix"] = folder + "/"

        res = client.storage.from_(bucket).list(folder, options)
        data = res if isinstance(res, list) else res.get("data", [])

        for obj in data:
            if not isinstance(obj, dict) or not obj.get("name"):
                continue
            
            if obj["name"] == folder or obj["name"].endswith(".keep"):
                continue

            if folder:
                full_path = f"{folder}/{obj['name']}"
            else:
                full_path = obj["name"]

            if obj.get("metadata") is None:
                contents.append({
                    "name": obj["name"],
                    "type": "folder",
                    "path": full_path,
                    "size": 0
                })
            else:
                contents.append({
                    "name": obj["name"],
                    "type": "file",
                    "path": full_path,
                    "size": obj.get("metadata", {}).get("size", 0)
                })

    except Exception as err:
        flash(f"Error listing contents: {err}")

    breadcrumbs = get_breadcrumbs(folder)
    current_bucket_public = is_public_bucket(bucket)

    return render_template("index.html",
                           contents=contents,
                           bucket_name=bucket,
                           current_folder=folder,
                           breadcrumbs=breadcrumbs,
                           buckets=buckets,
                           current_bucket_public=current_bucket_public)


@app.route("/upload/<bucket>", methods=["POST"])
def upload_file(bucket):   
    file = request.files.get("file")
    folder = normalize_path(request.form.get("folder", ""))

    if not file:
        flash("No file selected.")
        return redirect(url_for("index", bucket=bucket, folder=folder))

    try:
        
        client = get_client_for_bucket(bucket)
        
        if folder:
            path = f"{folder}/{file.filename}"
        else:
            path = file.filename
            
        res = client.storage.from_(bucket).upload(path, file.read())

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
        
        client = get_client_for_bucket(bucket)
        
        if parent:
            folder_path = f"{parent}/{name}"
        else:
            folder_path = name
            
        keep_file_path = f"{folder_path}/.keep"
        res = client.storage.from_(bucket).upload(keep_file_path, b"")

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
        
        client = get_client_for_bucket(bucket)
        
        res = client.storage.from_(bucket).remove([path])
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
        
        client = get_client_for_bucket(bucket)
        
        res = client.storage.from_(bucket).list(folder_path, {"limit": 1000})
        items = res if isinstance(res, list) else res.get("data", [])
        
        to_delete = []
        to_delete.append(f"{folder_path}/.keep")
        
        for item in items:
            if isinstance(item, dict) and item.get("name"):
                file_path = f"{folder_path}/{item['name']}"
                to_delete.append(file_path)

        if to_delete:
            result = client.storage.from_(bucket).remove(to_delete)
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
        
        client = get_client_for_bucket(bucket)
        
        content = client.storage.from_(bucket).download(path)
        if isinstance(content, dict) and content.get("error"):
            flash(f"Download failed: {content['error']['message']}")
        else:
            res = client.storage.from_(bucket).upload(new_path, content)
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
    
        client = get_client_for_bucket(bucket)
        
        content = client.storage.from_(bucket).download(path)
        if isinstance(content, dict) and content.get("error"):
            flash(f"Download failed: {content['error']['message']}")
            return redirect(url_for("index", bucket=bucket, folder=folder))

        uploaded = client.storage.from_(bucket).upload(new_path, content)
        if isinstance(uploaded, dict) and uploaded.get("error"):
            flash(f"Move failed: {uploaded['error']['message']}")
            return redirect(url_for("index", bucket=bucket, folder=folder))

        deleted = client.storage.from_(bucket).remove([path])
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
        
        client = get_client_for_bucket(bucket)
        
        res = client.storage.from_(bucket).create_signed_url(path, 3600)
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
    is_public = request.form.get("is_public") == "on"
    current_bucket = request.form.get("current_bucket", "my-bucket")
    
    if not name:
        flash("Bucket name required.")
        return redirect(url_for("index", bucket=current_bucket))

    try:
        
        bucket_options = {
            "public": is_public
        }
        
        res = sb_admin.storage.create_bucket(name, options=bucket_options)
        if isinstance(res, dict) and res.get("error"):
            flash(f"Bucket creation failed: {res['error']['message']}")
        else:
            bucket_type = "public" if is_public else "private"
            flash(f"Bucket '{name}' created successfully as {bucket_type}!")
            return redirect(url_for("index", bucket=name))
    except Exception as err:
        flash(f"Error creating bucket: {err}")
    
    return redirect(url_for("index", bucket=current_bucket))


@app.route("/toggle_bucket_publicity/<bucket>")
def toggle_bucket_publicity(bucket):
    """Toggle bucket between public and private"""
    if not bucket:
        flash("Bucket name required.")
        return redirect(url_for("index"))

    try:
        current_public = is_public_bucket(bucket)
        new_public = not current_public
        
        
        res = sb_admin.storage.update_bucket(bucket, {"public": new_public})
        if isinstance(res, dict) and res.get("error"):
            flash(f"Failed to update bucket: {res['error']['message']}")
        else:
            status = "public" if new_public else "private"
            flash(f"Bucket '{bucket}' is now {status}!")
    except Exception as err:
        flash(f"Error updating bucket: {err}")
    
    return redirect(url_for("index", bucket=bucket))


@app.route("/delete_bucket/<bucket>")
def delete_bucket(bucket):   
    if not bucket:
        flash("Bucket name required.")
        return redirect(url_for("index"))

    try:
        res = sb_admin.storage.delete_bucket(bucket)
        if isinstance(res, dict) and res.get("error"):
            flash(f"Bucket deletion failed: {res['error']['message']}")
        else:
            flash(f"Bucket '{bucket}' deleted successfully!")
            
            buckets = get_buckets()
            default_bucket = "my-bucket"
            if buckets and len(buckets) > 0:
                first_bucket = buckets[0]
                if hasattr(first_bucket, 'name'):
                    default_bucket = first_bucket.name
                elif isinstance(first_bucket, dict):
                    default_bucket = first_bucket.get("name", "my-bucket")
                else:
                    default_bucket = str(first_bucket)
            return redirect(url_for("index", bucket=default_bucket))
    except Exception as err:
        flash(f"Error deleting bucket: {err}")
    
    return redirect(url_for("index", bucket=bucket))


@app.route("/list_buckets")
def list_buckets():   
    try:
        buckets = get_buckets()
        bucket_info = []
        for bucket in buckets:
            if hasattr(bucket, 'name'):
                bucket_info.append({
                    "name": bucket.name,
                    "id": getattr(bucket, 'id', 'N/A'),
                    "created_at": getattr(bucket, 'created_at', 'N/A'),
                    "public": getattr(bucket, 'public', False)
                })
            elif isinstance(bucket, dict):
                bucket_info.append({
                    "name": bucket.get("name", "Unknown"),
                    "id": bucket.get("id", "N/A"),
                    "created_at": bucket.get("created_at", "N/A"),
                    "public": bucket.get("public", False)
                })
            else:
                bucket_info.append({
                    "name": str(bucket),
                    "id": "N/A",
                    "created_at": "N/A",
                    "public": False
                })
        flash(f"Found {len(bucket_info)} buckets. Check console for details.")
        print("Available buckets:", bucket_info)
    except Exception as err:
        flash(f"Error listing buckets: {err}")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)