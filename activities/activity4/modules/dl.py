import os

from flask import session, render_template, request, abort, url_for
from werkzeug.exceptions import Forbidden
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.deep_link_resource import DeepLinkResource
import json

from utils import get_lti_config_path, get_launch_data_storage

def register(app):
    def load_courses():
        # Load the courses from the JSON file
        courses_path =  os.path.join(app.root_path, '..', 'configs', 'resources.json')
        with open(courses_path) as f:
            courses = json.load(f)
        return courses

    @app.route('/deeplink/', methods=['GET'])
    def deeplink():
        # Get launch data from session
        launch_data = session.get('launch_data', {})
        launch_id = session.get('launch_id', '')

        courses = load_courses()
        
        tpl_kwargs = {
            'page_title': "Deeplinking",
            "courses": courses,
            'launch_id': launch_id,
            'target_link_uri': launch_data.get('https://purl.imsglobal.org/spec/lti/claim/target_link_uri', ''),
            'user_data': {
                'sub': launch_data.get('sub', ''),
                'name': launch_data.get('name', ''),
                'family_name': launch_data.get('family_name', ''),
                'given_name': launch_data.get('given_name', ''),
                'email': launch_data.get('email', ''),
                'sourced_id': launch_data.get('https://purl.imsglobal.org/spec/lti/claim/lis', '{}').get('person_sourcedid', ''),
            },
            'context_data': {
                **launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context', {}),
                'sourced_id': launch_data.get('https://purl.imsglobal.org/spec/lti/claim/lis', {}).get('course_section_sourcedid', '')
            },
            'user_roles': launch_data.get('https://purl.imsglobal.org/spec/lti/claim/roles', []),
            'resource_link': launch_data.get('https://purl.imsglobal.org/spec/lti/claim/resource_link', {})
        }
        return render_template("deeplink.html", **tpl_kwargs)
    

    @app.route('/dl/<resource_id>/', methods=['GET', 'POST'])
    def deeplink_response(resource_id):


        launch_id = session.get('launch_id', '')
        tool_conf = ToolConfJsonFile(get_lti_config_path(app))
        flask_request = FlaskRequest()
        launch_data_storage = get_launch_data_storage()
        message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf,
                                                    launch_data_storage=launch_data_storage)

        if not message_launch.is_deep_link_launch():
            raise Forbidden('Must be a deep link!')

        courses = load_courses()
        course = next((course for course in courses if course['id'] == int(resource_id)), None)
        
        if not course:
            abort(404, description=f"Course with ID {resource_id} not found")
        

        launch_url = url_for('home', _external=True) + '/resource/' + resource_id + '/'

        resource = DeepLinkResource()
        resource.set_url(launch_url) \
            .set_title(course.get("title", "Resource " + resource_id))
        
        # Get the optional 'model_id' from query parameters
        model_id = request.args.get('model_id', 'default')
        
        if model_id:
            resource.set_custom_params({'model_id': model_id})
        

        html = message_launch.get_deep_link().output_response_form([resource])
        return html


