/**
 * Validates a .star file content
 * @param {string} content - The content of the .star file
 * @returns {boolean} - Whether the content is valid
 */
export const validateStarFile = (content) => {
  // Add validation logic here
  return content.length > 0;
};

/**
 * Formats the duration for display
 * @param {number} duration - The duration value
 * @param {string} unit - The unit (seconds or loops)
 * @returns {string} - Formatted duration string
 */
export const formatDuration = (duration, unit) => {
  if (unit === 'seconds') {
    return duration > 60 
      ? `${Math.floor(duration / 60)}m ${duration % 60}s`
      : `${duration}s`;
  }
  return `${duration} loops`;
};

/**
 * Generates a unique ID for new programs
 * @returns {number} - A unique ID
 */
export const generateProgramId = () => {
  return Date.now() + Math.floor(Math.random() * 1000);
};

/**
 * Reorders an array of programs
 * @param {Array} programs - The array of programs
 * @param {number} fromIndex - Starting position
 * @param {number} toIndex - Ending position
 * @returns {Array} - The reordered array
 */
export const reorderPrograms = (programs, fromIndex, toIndex) => {
  const result = Array.from(programs);
  const [removed] = result.splice(fromIndex, 1);
  result.splice(toIndex, 0, removed);
  return result;
};

/**
 * Saves the programs to local storage
 * @param {Array} programs - The array of programs to save
 */
export const saveProgramsToStorage = (programs) => {
  localStorage.setItem('starPrograms', JSON.stringify(programs));
};

/**
 * Loads programs from local storage
 * @returns {Array} - The loaded programs or an empty array
 */
export const loadProgramsFromStorage = () => {
  const saved = localStorage.getItem('starPrograms');
  return saved ? JSON.parse(saved) : [];
};