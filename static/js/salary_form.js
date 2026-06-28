(function () {
    'use strict';

    const form = document.getElementById('salaryForm');
    if (!form) return;

    const earnings = ['basic_salary', 'house_rent', 'medical_allowance', 'transport_allowance', 'food_allowance', 'mobile_allowance', 'other_allowance'];
    const deductions = ['provident_fund', 'loan_deduction', 'advance_salary', 'other_deduction'];
    const grossOutput = document.getElementById('grossSalaryPreview');
    const netOutput = document.getElementById('netSalaryPreview');
    const warning = document.getElementById('salaryNetWarning');
    const submit = document.getElementById('salarySubmit');
    const formatter = new Intl.NumberFormat('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    function value(name) {
        const input = document.getElementById('id_' + name);
        return Math.max(0, Number.parseFloat(input && input.value) || 0);
    }

    function calculate() {
        const gross = earnings.reduce((total, name) => total + value(name), 0);
        const totalDeductions = deductions.reduce((total, name) => total + value(name), 0);
        const net = gross - totalDeductions;
        grossOutput.textContent = '৳' + formatter.format(gross);
        netOutput.textContent = '৳' + formatter.format(net);
        const invalid = net < 0;
        warning.classList.toggle('show', invalid);
        submit.disabled = invalid;
    }

    earnings.concat(deductions).forEach(function (name) {
        const input = document.getElementById('id_' + name);
        if (input) input.addEventListener('input', calculate);
    });
    calculate();
}());
