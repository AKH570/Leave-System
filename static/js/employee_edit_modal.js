(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const modalElement = document.getElementById('employeeEditModal');
        const modalBody = document.getElementById('employeeEditModalBody');
        const toastElement = document.getElementById('employeeSuccessToast');
        if (!modalElement || !modalBody || typeof bootstrap === 'undefined') return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        const toast = toastElement ? bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 4500 }) : null;
        const loadingHtml = modalBody.innerHTML;

        async function responseJson(response) {
            const contentType = response.headers.get('content-type') || '';
            if (response.redirected || !contentType.includes('application/json')) {
                throw new Error('Your session may have expired. Refresh the page and try again.');
            }
            const data = await response.json();
            return { response: response, data: data };
        }

        function showLoadError(message) {
            modalBody.innerHTML = '<div class="alert alert-danger mb-0" role="alert">' +
                '<strong>Unable to load employee.</strong><br>' + escapeHtml(message) + '</div>';
        }

        function escapeHtml(value) {
            const node = document.createElement('div');
            node.textContent = value || '';
            return node.innerHTML;
        }

        document.addEventListener('click', async function (event) {
            const editButton = event.target.closest('.js-employee-edit');
            if (!editButton) return;

            event.preventDefault();
            modalBody.innerHTML = loadingHtml;
            modal.show();

            try {
                const result = await responseJson(await fetch(editButton.href, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json',
                    },
                    credentials: 'same-origin',
                }));
                if (!result.response.ok || !result.data.ok) {
                    throw new Error(result.data.message || 'The employee form could not be loaded.');
                }
                modalBody.innerHTML = result.data.html;
            } catch (error) {
                showLoadError(error.message);
            }
        });

        modalBody.addEventListener('click', async function (event) {
            const trigger = event.target.closest('.js-add-department');
            const cancelButton = event.target.closest('.js-cancel-department');
            const createButton = event.target.closest('.js-create-department');

            if (trigger) {
                const panel = trigger.parentElement.querySelector('.employee-quick-department');
                const opening = panel.classList.contains('d-none');
                panel.classList.toggle('d-none', !opening);
                trigger.setAttribute('aria-expanded', opening ? 'true' : 'false');
                if (opening) panel.querySelector('input').focus();
                return;
            }

            if (cancelButton) {
                const panel = cancelButton.closest('.employee-quick-department');
                panel.classList.add('d-none');
                panel.parentElement.querySelector('.js-add-department').setAttribute('aria-expanded', 'false');
                panel.querySelector('.employee-quick-department-feedback').textContent = '';
                return;
            }

            if (!createButton) return;
            const panel = createButton.closest('.employee-quick-department');
            const field = panel.closest('.employee-modal-field');
            const input = panel.querySelector('input');
            const feedback = panel.querySelector('.employee-quick-department-feedback');
            const name = input.value.trim();
            feedback.textContent = '';
            feedback.classList.remove('is-success');
            input.classList.remove('is-invalid');

            if (!name) {
                feedback.textContent = 'Enter a department name.';
                input.classList.add('is-invalid');
                input.focus();
                return;
            }

            const triggerButton = field.querySelector('.js-add-department');
            const employeeForm = createButton.closest('#employeeEditForm');
            const requestData = new FormData();
            requestData.append('name', name);
            requestData.append('csrfmiddlewaretoken', employeeForm.querySelector('[name=csrfmiddlewaretoken]').value);
            createButton.disabled = true;

            try {
                const result = await responseJson(await fetch(triggerButton.dataset.createUrl, {
                    method: 'POST',
                    body: requestData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json',
                    },
                    credentials: 'same-origin',
                }));
                if (!result.response.ok || !result.data.ok) {
                    const errors = result.data.errors || {};
                    throw new Error((errors.name || errors.__all__ || ['Unable to add this department.'])[0]);
                }

                const department = result.data.department;
                const departmentSelect = field.querySelector('select[name=department]');
                let option = departmentSelect.querySelector('option[value="' + department.id + '"]');
                if (!option) {
                    option = new Option(department.name, department.id);
                    departmentSelect.add(option);
                }
                departmentSelect.value = String(department.id);
                departmentSelect.dispatchEvent(new Event('change', { bubbles: true }));
                input.value = '';
                panel.classList.add('d-none');
                triggerButton.setAttribute('aria-expanded', 'false');
                const status = field.querySelector('.employee-department-created');
                status.textContent = result.data.message;
                window.setTimeout(function () { status.textContent = ''; }, 4500);
            } catch (error) {
                feedback.textContent = error.message;
                input.classList.add('is-invalid');
                input.focus();
            } finally {
                createButton.disabled = false;
            }
        });

        modalBody.addEventListener('submit', async function (event) {
            const form = event.target.closest('#employeeEditForm');
            if (!form) return;
            event.preventDefault();

            const saveButton = form.querySelector('.employee-modal-save');
            const spinner = saveButton.querySelector('.spinner-border');
            saveButton.disabled = true;
            spinner.classList.remove('d-none');

            try {
                const result = await responseJson(await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json',
                    },
                    credentials: 'same-origin',
                }));

                if (result.response.status === 422 && result.data.html) {
                    modalBody.innerHTML = result.data.html;
                    const firstInvalid = modalBody.querySelector('.is-invalid');
                    if (firstInvalid) firstInvalid.focus();
                    return;
                }
                if (!result.response.ok || !result.data.ok) {
                    throw new Error(result.data.message || 'The employee could not be updated.');
                }

                const rowContainer = document.createElement('tbody');
                rowContainer.innerHTML = result.data.row_html.trim();
                const updatedRow = rowContainer.firstElementChild;
                const oldRow = document.getElementById(updatedRow.id);
                if (oldRow) oldRow.replaceWith(updatedRow);

                if (result.data.stats) {
                    Object.keys(result.data.stats).forEach(function (key) {
                        const target = document.querySelector('[data-employee-stat="' + key + '"]');
                        if (target) target.textContent = result.data.stats[key];
                    });
                }

                modal.hide();
                const message = document.getElementById('employeeSuccessMessage');
                if (message) message.textContent = result.data.message;
                if (toast) toast.show();
            } catch (error) {
                let alert = form.querySelector('.employee-submit-error');
                if (!alert) {
                    alert = document.createElement('div');
                    alert.className = 'alert alert-danger employee-submit-error';
                    alert.setAttribute('role', 'alert');
                    form.prepend(alert);
                }
                alert.textContent = error.message;
            } finally {
                if (document.body.contains(saveButton)) {
                    saveButton.disabled = false;
                    spinner.classList.add('d-none');
                }
            }
        });

        modalElement.addEventListener('hidden.bs.modal', function () {
            modalBody.innerHTML = loadingHtml;
        });
    });
}());
