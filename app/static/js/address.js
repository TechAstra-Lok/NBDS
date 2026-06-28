/**
 * address.js - Handles cascading dropdowns for Nepal Addresses
 * Requirements:
 * 1. A select element for Province (e.g., #perm_province, #curr_province)
 * 2. A select element for District (e.g., #perm_district, #curr_district)
 * 3. A select element for Local Level (e.g., #perm_local_level, #curr_local_level)
 */

document.addEventListener('DOMContentLoaded', function() {
    let addressData = null;

    // Fetch the address JSON data
    fetch('/static/data/nepal_address.json')
        .then(response => response.json())
        .then(data => {
            addressData = data;
            // Initialize all address dropdown sets on the page
            initializeDropdowns('perm');
            initializeDropdowns('curr');
            initializeDropdowns(''); // For forms without perm/curr prefix (like blood request)
        })
        .catch(error => console.error('Error loading address data:', error));

    function initializeDropdowns(prefix) {
        const provinceId = prefix ? `#${prefix}_province` : '#province';
        const districtId = prefix ? `#${prefix}_district` : '#district';
        const localLevelId = prefix ? `#${prefix}_local_level` : '#local_level';

        const provinceSelect = document.querySelector(provinceId);
        const districtSelect = document.querySelector(districtId);
        const localLevelSelect = document.querySelector(localLevelId);

        if (!provinceSelect || !districtSelect) return; // Not all forms have these fields

        // Preserve selected values (from WTForms or previous submission)
        const selectedDistrict = districtSelect.getAttribute('data-selected') || districtSelect.value;
        const selectedLocalLevel = localLevelSelect ? (localLevelSelect.getAttribute('data-selected') || localLevelSelect.value) : null;

        provinceSelect.addEventListener('change', function() {
            populateDistricts(this.value, districtSelect, selectedDistrict);
            if (localLevelSelect) {
                // Clear local level when province changes
                localLevelSelect.innerHTML = '<option value="">-- Select Municipality --</option>';
            }
        });

        districtSelect.addEventListener('change', function() {
            if (localLevelSelect) {
                populateLocalLevels(this.value, localLevelSelect, selectedLocalLevel);
            }
        });

        // Trigger initial population if province is already selected
        if (provinceSelect.value) {
            populateDistricts(provinceSelect.value, districtSelect, selectedDistrict);
        }
    }

    function populateDistricts(provinceName, districtSelect, selectedDistrict) {
        districtSelect.innerHTML = '<option value="">-- Select District --</option>';
        if (!provinceName || !addressData) return;

        const province = addressData[provinceName];
        if (province) {
            // province is an object: { "DistrictName": ["Mun1", "Mun2"], ... }
            const districts = Object.keys(province).sort();
            districts.forEach(district => {
                const option = document.createElement('option');
                option.value = district;
                option.textContent = district;
                if (district === selectedDistrict) {
                    option.selected = true;
                }
                districtSelect.appendChild(option);
            });
            // Trigger change to populate local levels if district is pre-selected
            districtSelect.dispatchEvent(new Event('change'));
        }
    }

    function populateLocalLevels(districtName, localLevelSelect, selectedLocalLevel) {
        localLevelSelect.innerHTML = '<option value="">-- Select Municipality --</option>';
        if (!districtName || !addressData) return;

        // Find the district across all provinces
        let foundMunicipalities = null;
        for (const provKey in addressData) {
            const province = addressData[provKey];
            if (province[districtName]) {
                foundMunicipalities = province[districtName];
                break;
            }
        }

        if (foundMunicipalities) {
            foundMunicipalities.sort().forEach(mun => {
                const option = document.createElement('option');
                option.value = mun;
                option.textContent = mun;
                if (mun === selectedLocalLevel) {
                    option.selected = true;
                }
                localLevelSelect.appendChild(option);
            });
        }
    }
});
