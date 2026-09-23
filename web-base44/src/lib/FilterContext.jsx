import React, { createContext, useContext, useState } from 'react';
import { ALL_FILTERS } from '@/lib/mockData';

const FilterContext = createContext(null);

export function FilterProvider({ children }) {
  const [filters, setFilters] = useState({ ...ALL_FILTERS });
  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));
  const setMany = (patch) => setFilters((prev) => ({ ...prev, ...patch }));
  const reset = () => setFilters({ ...ALL_FILTERS });
  return (
    <FilterContext.Provider value={{ filters, setFilters, setFilter, setMany, reset }}>
      {children}
    </FilterContext.Provider>
  );
}

export const useFilters = () => {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
};