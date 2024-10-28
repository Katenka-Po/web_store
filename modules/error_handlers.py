from flask import request, session, render_template


def create_error_handlers(app, logger):
    error_explanations = {
        400: "The server could not understand the request due to invalid syntax.",
        401: "The request has not been applied because it lacks valid authentication credentials for the target resource.",
        403: "Access to the requested resource is forbidden.",
        404: "The server cannot find the requested page.",
        429: "Too many requests. Please try again later.",
        491: "The server cannot handle the request due to a temporary overloading or maintenance of the server.",
        500: "The server has encountered a situation it doesn't know how to handle."
    }

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(429)
    @app.errorhandler(500)
    def handle_error(e):
        error_code = e.code if hasattr(e, 'code') else 500
        ip = request.remote_addr

        error_message = f"Error type: {error_code}\n{error_explanations.get(error_code, 'Error!')}\nIP: {ip}"

        logger.log(level=1, msg=error_message.replace('<br>', '\n'))

        request_url = request.url
        dont_show = 'user_id' not in session

        return render_template('error_page.html', error=error_message,
                               request_url=request_url, dont_show=dont_show), error_code
