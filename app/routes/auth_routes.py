from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from app.services.auth_service import AuthService


auth_bp = Blueprint(
    "auth",
    __name__
)

auth_service = AuthService()


@auth_bp.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if "user_id" in session:
        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        try:
            user = auth_service.register(
                full_name=request.form.get(
                    "full_name",
                    ""
                ),
                email=request.form.get(
                    "email",
                    ""
                ),
                phone=request.form.get(
                    "phone",
                    ""
                ),
                password=request.form.get(
                    "password",
                    ""
                )
            )

            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_role"] = user["role"]

            flash(
                "Cuenta creada correctamente.",
                "success"
            )

            return redirect(
                url_for("index")
            )

        except ValueError as error:

            flash(
                str(error),
                "danger"
            )

        except Exception as error:

            print(error)

            flash(
                "Ocurrió un error al crear la cuenta.",
                "danger"
            )

    return render_template(
        "register.html"
    )


@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "user_id" in session:
        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        user = auth_service.login(
            email,
            password
        )

        if not user:

            flash(
                "Correo o contraseña incorrectos.",
                "danger"
            )

            return render_template(
                "login.html"
            )

        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        session["user_role"] = user["role"]

        flash(
            f"Bienvenido, {user['full_name']}.",
            "success"
        )

        return redirect(
            url_for("index")
        )

    return render_template(
        "login.html"
    )


@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("auth.login")
    )