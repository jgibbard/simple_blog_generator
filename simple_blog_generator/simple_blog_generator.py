#!/usr/bin/env python3

import datetime
import json
import os
import pathlib
import shutil
import sys

import jinja2
import markdown


class SimpleBlogGenerator():

    def __init__(self,
                 content_directory="content",
                 theme="basic",
                 output_directory="output",
                 default_author="Joe Bloggs",
                 website_name="My Blog",
                 website_description="Website",
                 copyright=None,
                 date_format="%Y/%m/%d",
                 category_page_post_limit=10,
                 index_page_post_limit=5):

        self.content_directory = content_directory
        themes_directory = os.path.join(str(pathlib.Path(__file__).parent), "themes")
        theme_directory = os.path.join(themes_directory, theme)
        self.templates_directory = os.path.join(theme_directory, "templates")
        self.static_directory = os.path.join(theme_directory, "static")
        self.output_directory = output_directory
        self.output_permissions = 0o755

        self.default_author = default_author
        self.website_name = website_name
        self.website_description = website_description
        self.date_format = date_format
        self.category_page_post_limit = int(category_page_post_limit)
        self.index_page_post_limit = int(index_page_post_limit)
        # Use a copyright statement if provided, otherwise use current year and default author
        if copyright:
            self.copyright = copyright
        else:
            self.copyright = f"Copyright {datetime.datetime.now().year} {self.default_author}"
        
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath=self.templates_directory))

        # Read the directory names in the content directory
        # Each directory is treated as a category
        self.categories = next(os.walk(self.content_directory))[1]
        # There must be at least one category
        assert len(self.categories) > 0

        self.posts = None
        self.sorted_posts = None

    def generate(self):
        # Clear previously generated output files
        self.clean()
        # Get the HTML and metadata for all posts
        self._get_posts()
        # Divide posts into categories and sort in date order
        # Discards unused categories
        self._sort_posts()
        # Copy global static assets to output directory
        self._copy_static_assets()
        # Copy static assets for all posts
        self._copy_post_assets()
        # Generate HTML page for each post
        self._generate_post_pages()
        # Generate the category pages
        self._generate_category_pages()
        # Generate the home page
        self._generate_home_pages()

    def get_most_recent_post_titles(self, category, number, offset=0):
        # Get the N most recent posts titles in a specified category
        # Validate inputs
        assert number != 0
        assert category in self.categories or category == "all_posts"
        # If the posts haven't been sorted yet, then sort them
        if not self.sorted_posts:
           self._sort_posts()
        # Get a list of just the post titles from the list of (title, date) tuples
        post_titles = [post[0] for post in self.sorted_posts[category]]
        number_of_posts = len(post_titles)
        # Catch case where there are no posts in the category
        if number_of_posts == 0:
            return list()
        # Make sure the offset doesn't exceed the size of the list
        assert offset < number_of_posts
        # Return a list of the most recent posts
        if number_of_posts >= (number + offset):
            return post_titles[offset:offset+number]
        else:
            # If there is not as many posts are requested, then return as many as possible
            return post_titles[offset:]

    def get_most_recent_posts(self, category, number, offset=0):
        # Get the N most recent posts in a specified category
        # Validate inputs
        assert number != 0
        assert category in self.categories or category == "all_posts"
        # If the posts haven't been sorted yet, then sort them
        if not self.sorted_posts:
           self._sort_posts()
        # Get titles of the most recent posts in a given category
        post_titles = self.get_most_recent_post_titles(category, number, offset)
        # Construct dictionary of the most recent posts
        return [self.posts[post_title]["post"] for post_title in post_titles]

    def clean(self):        
        # Clear post cache
        self.posts = None
        self.sorted_posts = None
        # Delete all files in the output directory, but not the directory itself
        if os.path.isdir(self.output_directory):            
            for root, dirs, files in os.walk(self.output_directory):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))
        else:
            # If output directory doesn't exist, create it
            os.mkdir(self.output_directory, self.output_permissions)

    def _get_posts(self):
        # Dictionary to store all posts
        self.posts = {}
        # Find all posts and get their locations
        for category in self.categories:
            category_directory = os.path.join(self.content_directory, category)        
            post_path_strings = self._get_post_file_paths(category_directory)
            for path_string in post_path_strings:
                path = pathlib.Path(path_string)
                post_title = path.stem.lower()
                # Check for more than one post with the same name
                if post_title in self.posts:
                    print("Error: Post name must be unique")
                    exit(1)                
                # Get the path the assets directory associated with the post
                # Check if the file is within a directory of the same name
                if path.parent.name.lower() == post_title:
                    asset_path = str(path.parent)
                # Check if there is a directory of the same name as the post
                elif os.path.isdir(os.path.join(category_directory, post_title)):
                    asset_path = os.path.join(category_directory, post_title)
                else:
                    # No assets for this post
                    asset_path = None
                
                meta, html = self._read_markdown(path_string)
                # Update dictionary with post details                
                self.posts[post_title] = {"path": path_string,
                                          "category": category,
                                          "assets": asset_path}
                # Set default values
                self.posts[post_title]["post"] = {"local_styles":[],
                                                  "global_styles":[],
                                                  "author":self.default_author,
                                                  "description":"",
                                                  "main_image":""}
                # Required post metadata
                if "title" in meta:
                    self.posts[post_title]["post"]["title"] = meta["title"][0]
                else:
                    print(f"No title metadata specified in {path_string}")
                    exit(1)
                if "date" in meta:
                    self.posts[post_title]["post"]["date"] = meta["date"][0]
                else:
                    print(f"No date metadata specified in {path_string}")
                    exit(1)
                # Add the post HTML
                self.posts[post_title]["post"]["article"] = html
                # Add the page URL
                self.posts[post_title]["post"]["url"] = post_title
                # Optional post metadata
                if "global_styles" in meta:
                    self.posts[post_title]["post"]["global_styles"] = meta["global_styles"]
                if "local_styles" in meta:
                    self.posts[post_title]["post"]["local_styles"] = meta["local_styles"]
                if "author" in meta:
                    self.posts[post_title]["post"]["author"] = meta["author"][0]
                if "description" in meta:
                    self.posts[post_title]["post"]["description"] = meta["description"][0]
                if "main_image" in meta:
                    self.posts[post_title]["post"]["main_image"] = meta["main_image"][0]

    def _sort_posts(self):
        # Create a dictionary of lists where the posts are split into categories and sorted by
        # post date.
        if not self.posts:
            self._get_posts()
        self.sorted_posts = {category : list() for category in self.categories}
        # Add all posts category
        self.sorted_posts["all_posts"] = list()
        # For each category extract the post names and dates
        for post_title, post_details in self.posts.items():
            date_string = post_details["post"]["date"]
            date = datetime.datetime.strptime(date_string, self.date_format)
            self.sorted_posts[post_details["category"]].append((post_title, date))
            self.sorted_posts["all_posts"].append((post_title, date))
        # Remove all categories with no posts
        self.categories = [
            category for category in self.categories if len(self.sorted_posts[category])]
        self.sorted_posts = {
            category:self.sorted_posts[category] for category in self.sorted_posts.keys() \
                if len(self.sorted_posts[category])}
        # Sort each category in date order with newest posts having lower indices
        for category in self.categories:
            self.sorted_posts[category] = sorted(
                self.sorted_posts[category], key=lambda elem : elem[1], reverse=True)
        # Also create an extra category of all posts and sort them all in date order.
        # This is used for the home pages.
        self.sorted_posts["all_posts"] = sorted(
                self.sorted_posts["all_posts"], key=lambda elem : elem[1], reverse=True)

    def _read_markdown(self, filename):
        # Open a markdown file and convert it to HTML
        with open(filename, "r") as f:
            md = markdown.Markdown(extensions=["meta","fenced_code", "codehilite", "attr_list"],
                                   extension_configs={"codehilite":{"guess_lang":False}})
            html = md.convert(f.read())
            meta = md.Meta
            return meta, html

    def _get_post_file_paths(self, search_directory):
        # Locate all markdown files in the content directory
        posts = []
        for root, _, filenames in os.walk(search_directory):
            for filename in filenames:
                if filename.endswith(".md"):
                    posts.append(os.path.join(root, filename))
        return posts

    def _copy_static_assets(self):
        # Copy the global static assets (logos, CSS files, javascript etc.) over to the output
        # directory.
        if os.path.isdir(self.static_directory):
            static_assets_output_directory = os.path.join(self.output_directory, "static")
            shutil.copytree(self.static_directory, static_assets_output_directory)

    def _copy_post_assets(self):
        # Copy all the post assets (typically images, CSS files and javascript files) over to the
        # output directory.
        assert self.posts is not None
        for post_title, post_details in self.posts.items():
            # If there is an assets folder for the post then copy everything over to output dir
            if post_details["assets"]:
                assets_output_directory = os.path.join(self.output_directory, post_title)
                shutil.copytree(post_details["assets"],
                                assets_output_directory,
                                ignore=shutil.ignore_patterns("*.md"))
            # Otherwise just make the post directory
            else:
                os.mkdir(os.path.join(self.output_directory, post_title), self.output_permissions)

    def _get_page_name(self, page_number, number_of_pages):
        # Get the current, next, and previous page names
        # Used when setting the back and forward links on paginated pages
        # Set the page name
        if page_number == 0:
            page_name = "index.html"
        else:
            page_name = f"page{page_number}.html"
        # Set the page name for the previous page link
        if page_number == 0:
            previous_page = None
        elif page_number == 1:
            previous_page = "index.html"
        else:
            previous_page = f"page{page_number-1}.html"
        # Set the page name for the next page link
        if page_number == (number_of_pages - 1):
            next_page = None
        else:
            next_page = f"page{page_number+1}.html"
        # Return page link names
        return page_name, previous_page, next_page

    def _generate_post_pages(self):
        # Generate all the post pages
        assert self.posts is not None
        post_template = self.template_env.get_template("post.html")
        for post_title, post_details in self.posts.items():
            output_file = os.path.join(self.output_directory, post_title, "index.html")
            self._write_html_file(output_file,
                post_template.render(
                    copyright=self.copyright,
                    website_name=self.website_name,
                    base_url="..",
                    categories=self.categories,
                    page_category=post_details["category"],
                    **post_details["post"]
                    )
                )

    def _generate_category_page(self, category, page_name, previous_page, next_page, offset):
        # Generate a single category page
        assert self.posts is not None
        assert self.sorted_posts is not None
        # Get the posts that will appear on this page
        posts_on_this_page = self.get_most_recent_posts(
            category, self.category_page_post_limit, offset)
        # Generate each category page
        category_template = self.template_env.get_template("category.html")
        output_file = os.path.join(self.output_directory, category.lower(), page_name)
        self._write_html_file(output_file,
            category_template.render(
                copyright=self.copyright,
                website_name=self.website_name,
                base_url="..",
                categories=self.categories,
                author=self.default_author,
                title=category,
                description=f"Posts about {category}.",
                page_category=category,
                previous_page=previous_page,
                next_page=next_page,
                posts=posts_on_this_page
                )
            )

    def _generate_category_pages(self):
        # Generate all category pages
        assert self.posts is not None
        assert self.sorted_posts is not None
        for category in self.categories:
            # Create category directory
            category_directory = os.path.join(self.output_directory, category.lower())
            if not os.path.isdir(category_directory):
                os.mkdir(category_directory, self.output_permissions)
            # Get total number of posts in the category
            number_of_posts = len(self.sorted_posts[category])
            # Get the number of pages required to show all the posts within the category
            number_of_pages = number_of_posts // self.category_page_post_limit
            if number_of_posts % self.category_page_post_limit:
                number_of_pages += 1
            # Generate each category page
            for page_number in range(number_of_pages):
                # Set the page name for the current, previous, and next page links
                page_name, previous_page, next_page = self._get_page_name(page_number,
                                                                          number_of_pages)
                # Offset in the list of posts to include on a specific page
                offset = page_number * self.category_page_post_limit
                # Generate a category page
                self._generate_category_page(category, page_name, previous_page, next_page, offset)

    def _generate_home_pages(self):
        # Generate all home pages
        assert self.posts is not None
        assert self.sorted_posts is not None      
        # Get total number of posts
        number_of_posts = len(self.sorted_posts["all_posts"])
        # Get the number of pages required to show all the posts
        number_of_pages = number_of_posts // self.index_page_post_limit
        if number_of_posts % self.index_page_post_limit:
            number_of_pages += 1
        # Generate each index page
        for page_number in range(number_of_pages):
            # Set the page name for the current, previous, and next page links
            page_name, previous_page, next_page = self._get_page_name(page_number, number_of_pages)
            # Offset in the list of posts to include on a specific page
            offset = page_number * self.index_page_post_limit
            # Get the posts that will appear on this page
            posts_on_this_page = self.get_most_recent_posts(
                "all_posts", self.index_page_post_limit, offset)
            # Generate an index page
            home_template = self.template_env.get_template("home.html")
            output_file = os.path.join(self.output_directory, page_name)
            self._write_html_file(output_file,
                home_template.render(
                    copyright=self.copyright,
                    website_name=self.website_name,
                    base_url="",
                    categories=self.categories,
                    page_category="Home",
                    author=self.default_author,
                    title=self.website_name,
                    description=self.website_description,
                    previous_page=previous_page,
                    next_page=next_page,
                    posts=posts_on_this_page
                    )
                )

    def _write_html_file(self, file_name, html_string):
        # Write the HTML files to the output directory 
        with open(file_name, "w") as f:
            f.write(html_string)