import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from './utils'

describe('App Shell & Route Navigation', () => {
  it('a. visiting /analyze renders the app shell and the Analyze page header', () => {
    renderWithProviders(undefined, { initialEntries: ['/analyze'] })

    // Check App Shell header and navigation landmarks
    expect(screen.getByRole('banner')).toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByText('PPE Guardian').length).toBeGreaterThan(0)

    // Check Analyze page title and placeholder description
    expect(screen.getByRole('heading', { level: 1, name: 'Analyze' })).toBeInTheDocument()
    expect(
      screen.getByText(/The Analyze page is built in Steps F4 and F5/i),
    ).toBeInTheDocument()
  })

  it('b. clicking each sidebar link shows the matching page header', async () => {
    const user = userEvent.setup()
    renderWithProviders(undefined, { initialEntries: ['/analyze'] })

    // Starts on Analyze
    expect(screen.getByRole('heading', { level: 1, name: 'Analyze' })).toBeInTheDocument()

    const sidebarNav = screen.getByRole('navigation', { name: 'Main Navigation' })

    // 1. Navigate to Violations
    const violationsLink = sidebarNav.querySelector('a[href="/violations"]')
    expect(violationsLink).toBeInTheDocument()
    await user.click(violationsLink!)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Violations' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/The Violations page is built in Step F7/i),
    ).toBeInTheDocument()

    // 2. Navigate to Results
    const resultsLink = sidebarNav.querySelector('a[href="/results"]')
    expect(resultsLink).toBeInTheDocument()
    await user.click(resultsLink!)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Results' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/The Results page is built in Step F10/i)).toBeInTheDocument()

    // 3. Navigate to Workers
    const workersLink = sidebarNav.querySelector('a[href="/workers"]')
    expect(workersLink).toBeInTheDocument()
    await user.click(workersLink!)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Workers' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/The Workers page is built in Step F6/i)).toBeInTheDocument()

    // 4. Navigate back to Analyze
    const analyzeLink = sidebarNav.querySelector('a[href="/analyze"]')
    expect(analyzeLink).toBeInTheDocument()
    await user.click(analyzeLink!)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Analyze' }),
    ).toBeInTheDocument()
  })

  it('c. an unknown URL shows the NotFound page', () => {
    renderWithProviders(undefined, { initialEntries: ['/nonexistent-route-xyz'] })

    expect(
      screen.getByRole('heading', { level: 1, name: 'Page Not Found' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Return to Analyze/i)).toBeInTheDocument()
  })
})
