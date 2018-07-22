from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db

from lxml.html.clean import clean_html


bp = Blueprint('blog', __name__)


@bp.route('/')
def index():
    """Show all the posts, most recent first."""
    db = get_db()
    if g.user :
        posts = db.execute(
            'SELECT p.id, title, body, visibility, created, author_id, username'
            ' FROM post p JOIN user u ON p.author_id = u.id'
            ' WHERE visibility IS NULL OR visibility = ? or author_id = ?'
            ' ORDER BY created DESC',
            (g.user['id'], g.user['id'])
        ).fetchall()
    else:
        posts = db.execute(
            'SELECT p.id, title, body, visibility, created, author_id, username'
            ' FROM post p JOIN user u ON p.author_id = u.id'
            ' WHERE visibility IS NULL'
            ' ORDER BY created DESC'
        ).fetchall()
    return render_template('blog/index.html', posts=posts)


def get_post(id, check_author=True):
    """Get a post and its author by id.

    Checks that the id exists and optionally that the current user is
    the author.

    :param id: id of post to get
    :param check_author: require the current user to be the author
    :return: the post with author information
    :raise 404: if a post with the given id doesn't exist
    :raise 403: if the current user isn't the author
    """
    post = get_db().execute(
        'SELECT p.id, title, body, created, visibility, author_id, username'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if post is None:
        abort(404, "پستی با شماره {0} وجود ندارد.".format(id))

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post

def get_comment(id, check_author=True):
    """Get a comment and its post and its author by id.

    Checks that the id exists and optionally that the current user is
    the author of its post.

    :param id: id of comment to get
    :param check_author: require the current user to be the author
    :return: the comment with its post and author information
    :raise 404: if a comment with the given id doesn't exist
    :raise 403: if the current user isn't the author
    """
    comment = get_db().execute(
        'SELECT c.id, c.title, c.body, c.created, c.post_id, p.title, p.body, p.visibility, p.created, p.author_id, u.username'
        ' FROM comment c'
        '  JOIN post p ON c.post_id = p.id'
        '  JOIN user u ON p.author_id = u.id'
        ' WHERE c.id = ?',
        (id,)
    ).fetchone()

    if comment is None:
        abort(404, "نظری با شماره {0} وجود ندارد.".format(id))

    if check_author and comment['author_id'] != g.user['id']:
        abort(403)

    return comment


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    """Create a new post for the current user."""
    if request.method == 'POST':
        title = request.form['title']
        body = clean_html( request.form['body'] )
        visibility = request.form['visibility']
        error = None

        if not title:
            error = 'عنوان لازم است.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (title, body, visibility, author_id)'
                ' VALUES (?, ?, ?, ?)',
                (title, body, maybeNone(visibility), g.user['id'])
            )
            db.commit()
            return redirect(url_for('blog.index'))

    db = get_db()
    users = db.execute(
        'SELECT id, username'
        ' FROM user'
        ' ORDER BY id DESC'
    ).fetchall()
    return render_template('blog/create.html', users=users)



@bp.route('/post/<int:id>', methods=('GET', 'POST'))
def post(id):
    """View post and comments."""
    db = get_db()
    if g.user:
        post = db.execute(
            'SELECT p.id, title, body, visibility, created, author_id, username'
            ' FROM post p JOIN user u ON p.author_id = u.id'
            ' WHERE (visibility IS NULL OR visibility = ? OR author_id = ?) AND p.id = ?'
            ' ORDER BY created DESC',
            (g.user['id'], g.user['id'], id)
        ).fetchone()
    else:
        post = db.execute(
            'SELECT p.id, title, body, visibility, created, author_id, username'
            ' FROM post p JOIN user u ON p.author_id = u.id'
            ' WHERE visibility IS NULL AND p.id = ?'
            ' ORDER BY created DESC',
            (id,)
        ).fetchone()

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'عنوان لازم است.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO comment (title, body, post_id)'
                ' VALUES (?, ?, ?)',
                (title, body, post['id'])
            )
            db.commit()
        return redirect(url_for('blog.post', id=post['id']))

    comments = db.execute(
        'SELECT id, title, body, created, post_id'
        ' FROM comment'
        ' WHERE post_id = ?'
        ' ORDER BY created DESC',
        (post['id'],)
    ).fetchall()

    return render_template('blog/post.html', post=post, comments=comments)



def maybeNone(s):
    if s == 'NULL':
        return None
    return s

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    """Update a post if the current user is the author."""
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        visibility = request.form['visibility']
        error = None

        if not title:
            error = 'عنوان لازم است.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = ?, body = ?, visibility = ? WHERE id = ?',
                (title, body, maybeNone(visibility), id)
            )
            db.commit()
            return redirect(url_for('blog.index'))

    db = get_db()
    users = db.execute(
        'SELECT id, username'
        ' FROM user'
        ' ORDER BY id DESC'
    ).fetchall()
    return render_template('blog/update.html', post=post, users=users)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('blog.index'))

@bp.route('/<int:id>/deleteComment', methods=('POST',))
@login_required
def deleteComment(id):
    """Delete a comment.

    Ensures that the comment exists and that the logged in user is the
    author of the post.
    """
    comment = get_comment(id)
    url_for_post = url_for('blog.post', id=comment['post_id'])
    db = get_db()
    db.execute('DELETE FROM comment WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for_post)
















