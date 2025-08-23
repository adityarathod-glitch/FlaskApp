Imports

The code imports Flask (for the web application), Supabase client (to connect to storage), and the os module (for handling file paths).



Flask App Setup

The application is created using Flask.
A secret key is set for session handling and flash messages.



Supabase Configuration

Three Supabase credentials are defined:

Supabase URL: the project’s base URL.

Anon Key: used for regular client operations like file upload and download.

Service Role Key: used for admin-level operations like creating or deleting buckets.

Two clients are created:

sb: normal client using the anon key.

sb_admin: admin client using the service role key.



normalize_path

Utility function that cleans up folder paths. It removes unnecessary slashes so paths stay consistent.



get_breadcrumbs

Builds breadcrumb navigation for folders. For example, if the user is in photos/2024/events, it generates Root > photos > 2024 > events.


get_buckets

Fetches all available storage buckets from Supabase using the admin client. It ensures the result is always returned as a list.


index (homepage)

The main route of the app.

It checks the selected bucket and current folder.

It retrieves a list of all available buckets.

It fetches the contents of the current folder (files and subfolders).

It prepares data for breadcrumbs and contents.

Finally, it renders the index.html template to display everything.



upload_file

Handles file uploads into the selected bucket.

Reads the file from the form.

Decides the correct path (inside the current folder or at the root).

Uploads the file to Supabase storage.

Shows a success or error message.



create_folder

Creates a new folder inside a bucket.

Since Supabase doesn’t support empty folders, it uploads a hidden .keep file to force folder creation.

Shows success or error messages.



delete_file

Deletes a single file from the given bucket.

Reads the file path from query parameters.

Removes the file from Supabase storage.

Shows success or error messages.



delete_folder

Deletes an entire folder.

Lists all files inside the folder.

Collects them along with the .keep file.

Deletes them one by one.

Shows a success message if completed.



copy_file

Allows copying of a file to a new location in the same bucket.

On GET request: Shows a form with a suggested new filename.

On POST request: Downloads the file, re-uploads it to the new location, and shows success or error messages.



move_file

Moves a file from one location to another.

On GET request: Shows a form with a suggested new name.

On POST request: Downloads the file, uploads it to the new location, and deletes the original.

Shows appropriate messages depending on the result.



download_file

Creates a temporary signed URL for a file so it can be downloaded.

The signed link is valid for one hour.

If successful, redirects the user to that link (which starts the download).

If unsuccessful, shows an error message and redirects back.



create_bucket

Creates a new bucket.

Reads the bucket name from a form.

Uses the admin client to create it.

If successful, redirects to the new bucket view.

Otherwise, flashes an error message.



delete_bucket

Deletes a bucket.

Uses the admin client to remove the bucket.

If successful, picks another bucket as the default so the app does not break.

Shows either a success or error message.




list_buckets

Lists all buckets.

Fetches all available buckets.

Collects information like name, ID, and creation time.

Prints details in the server console.

Shows a flash message about how many buckets were found.




Application Runner

At the end, the Flask application is started on port 5001 with debug mode enabled.

Debug mode restarts the server automatically when code changes, and shows detailed error messages during development.






