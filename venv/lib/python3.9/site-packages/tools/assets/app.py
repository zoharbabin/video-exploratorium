from chalice import Chalice, Rate
from chalice_http_toolkit.content import ContentManager
from chalice_http_toolkit.cloudfront import CloudFront
import os
import traceback
from magic import Magic

app = Chalice(app_name='<app_name>')
app.api.binary_types.append('multipart/form-data')
app.api.binary_types.append('image/*')
app_dir = os.path.dirname(os.path.realpath(__file__))

chalicelib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'chalicelib')
<use_magic>

cm = ContentManager(os.path.join(chalicelib_dir, 'templates'), os.path.join(chalicelib_dir, 'static'), app<cm_use_magic>)
cm.set_static_handler_prefix('/static')
cf = CloudFront(cm, app)

@app.route('/static/{filename}')
def static_route(filename):
    """
    Serves content from the static directory set above
    """
    r = cf.static(filename, cache_control='public, must-revalidate, max-age=604800')
    return r

@app.route('/{proxy+}')
def page_not_found():
    """
    404 handler, this only works when deployed to a real Lambda instance.
    """
    try:
        return cm.html(cm.render_template('404.html'), status_code=404)
    except Exception as e:
        traceback.print_exc()

def render_index():
    return cf.template('index.html', cache_control='public, must-revalidate, max-age=604800')

@app.schedule(Rate(5, unit=Rate.MINUTES))
def keep_alive_index(event):
    """
    Keeps this function warm to enable snappy response time
    """
    print('keep alive')

@app.route('/')
def index():
    """
    Index handler
    """
    try:
        return render_index()
    except Exception as e:
        traceback.print_exc()
    return cm.html(cm.render_template('404.html'), status_code=404)